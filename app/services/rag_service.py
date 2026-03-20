"""
RAG 问答服务（含引用溯源、多轮对话、相关性过滤、流式输出）

流程：
  1. 问题向量化（DashScope TextEmbedding）
  2. ChromaDB 向量检索 top-5（含相关性距离阈值过滤）
  3. 格式化检索结果为带编号的参考上下文
  4. 拼入近期对话历史（多轮对话支持）
  5. DashScope Qwen-Plus 生成回答（支持流式/非流式）
  6. 返回 answer + sources（每条含 doc_id / filename / 结构化字段 / 摘要）
"""
import os
import re
from typing import Generator

import dashscope
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

if settings.DASHSCOPE_API_KEY:
    dashscope.api_key = settings.DASHSCOPE_API_KEY


# ── 向量化 ────────────────────────────────────────────────────

def _get_text_embeddings_sync(text: str) -> list:
    if not settings.DASHSCOPE_API_KEY:
        return [0.1] * 1536
    try:
        resp = dashscope.TextEmbedding.call(
            model=dashscope.TextEmbedding.Models.text_embedding_v1,
            input=text,
        )
        if resp.status_code == 200:
            return resp.output["embeddings"][0]["embedding"]
        logger.warning("embedding_failed", extra={"code": resp.status_code})
        return [0.1] * 1536
    except Exception as e:
        logger.warning("embedding_error", extra={"error": str(e)})
        return [0.1] * 1536


async def get_text_embeddings(text: str) -> list:
    return await run_in_threadpool(_get_text_embeddings_sync, text)


# ── 检索 ──────────────────────────────────────────────────────

# 相关性距离阈值（ChromaDB 默认距离算法 L2，值越小越相似）
# > 1.8 的结果视为不相关，不纳入上下文，避免"无关资料污染答案"
_RELEVANCE_THRESHOLD = 1.8


async def retrieve_context(question_vec: list, top_k: int = 5) -> list:
    """
    使用 ChromaDB 进行向量检索，并过滤距离超过阈值的不相关结果。
    返回列表，每条含 text / metadata / distance。
    """
    from app.services.vector_store.chroma import query_documents
    results = await run_in_threadpool(query_documents, question_vec, top_k)
    filtered = [r for r in results if r.get("distance", 0) <= _RELEVANCE_THRESHOLD]
    return filtered if filtered else results[:2]


# ── 上下文格式化 ──────────────────────────────────────────────

def _format_context(context_items: list) -> str:
    """将检索结果格式化为带编号的参考上下文，包含结构化元数据标注。"""
    parts = []
    for i, item in enumerate(context_items):
        meta = item.get("metadata", {})
        text = item.get("text", "")
        tags = []
        for key, label in [("time", "时间"), ("location", "地点"),
                            ("seller", "卖方"), ("buyer", "买方"),
                            ("price", "价格"), ("subject", "标的")]:
            v = str(meta.get(key, "")).strip()
            if v and v not in {"未识别", "未记载", "None", "null", ""}:
                tags.append(f"{label}：{v}")
        tag_str = "　".join(tags)
        header = f"[参考{i+1}]" + (f" （{tag_str}）" if tag_str else "")
        # 截取前 600 字，提供更充分的上下文
        excerpt = text[:600] + ("..." if len(text) > 600 else "")
        parts.append(f"{header}\n{excerpt}")
    return "\n\n".join(parts)


# ── 消息构建（共享逻辑）────────────────────────────────────────

def _build_messages(question: str, context_items: list, history=None) -> list:
    """构建 LLM API 所需的 messages 列表（供同步和流式共用）。"""
    system_msg = {
        "role": "system",
        "content": (
            "你是一位专研中国古代契约文书的智能问答助手，服务于古代地契文书知识图谱分析平台。\n"
            "知识库中存储了若干份经过 OCR 识别与结构化分析的地契文书，"
            "每份文书包含买卖双方、时间、地点、价格、标的等结构化信息。\n\n"
            "【回答准则】\n"
            "1. 以检索到的参考文书为主要依据，引用时在句末用 [参考N] 标注来源编号\n"
            "2. 比较多份文书时，逐条分析并给出总结，观点须有据可查\n"
            "3. 若参考资料中有明确记载，直接引用原文关键词，不过度推断\n"
            "4. 若知识库中无相关记录，如实告知「知识库中暂无相关记录」，"
            "   可结合历史背景知识补充说明，但须与知识库内容明确区分\n"
            "5. 回答结构清晰，必要时使用列表或分段，避免冗长重复\n"
            "6. 人名、地名、金额等保持原文写法，不做现代化转换\n"
            "7. 多轮对话时，结合历史上下文理解意图，代词指代须明确解析"
        ),
    }

    messages = [system_msg]

    if history:
        for turn in history[-8:]:
            if isinstance(turn, dict):
                role, content = turn.get("role", "user"), turn.get("content", "")
            else:
                role, content = getattr(turn, "role", "user"), getattr(turn, "content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

    if context_items:
        context_str = _format_context(context_items)
        user_content = f"【参考文书】\n{context_str}\n\n【问题】{question}"
    else:
        user_content = (
            f"【说明】知识库中暂未检索到与此问题直接相关的文书，"
            f"请根据通用古代契约文书知识作答，并注明系通识内容。\n\n【问题】{question}"
        )
    messages.append({"role": "user", "content": user_content})
    return messages


# ── 同步生成（非流式）────────────────────────────────────────

def _generate_answer_sync(
    question: str,
    context_items: list,
    history=None,
) -> str:
    if not settings.DASHSCOPE_API_KEY:
        return "未配置 DASHSCOPE_API_KEY，无法生成智能回答。"

    messages = _build_messages(question, context_items, history)

    try:
        response = dashscope.Generation.call(
            model="qwen-plus",
            messages=messages,
            result_format="message",
            max_tokens=1500,
        )
        if response.status_code == 200:
            try:
                return response.output.choices[0].message.content
            except (AttributeError, IndexError, TypeError):
                return response.output["choices"][0]["message"]["content"]
        logger.warning("llm_generation_failed", extra={"code": response.code})
        return f"生成回答失败（{response.code}），请稍后再试。"
    except Exception as e:
        logger.error("llm_generation_error", extra={"error": str(e)})
        return "生成过程发生错误，请稍后再试。"


async def generate_answer(question: str, context_items: list, history=None) -> str:
    return await run_in_threadpool(_generate_answer_sync, question, context_items, history)


# ── 流式生成（SSE）────────────────────────────────────────────

def _generate_answer_stream_chunks(
    question: str,
    context_items: list,
    history=None,
) -> Generator[str, None, None]:
    """
    同步生成器，逐块 yield 文本增量（用于 SSE 流式推送）。
    调用方需在线程池中运行此生成器。
    """
    if not settings.DASHSCOPE_API_KEY:
        yield "未配置 DASHSCOPE_API_KEY，无法生成智能回答。"
        return

    messages = _build_messages(question, context_items, history)

    try:
        responses = dashscope.Generation.call(
            model="qwen-plus",
            messages=messages,
            result_format="message",
            max_tokens=1500,
            stream=True,
            incremental_output=True,
        )
        for response in responses:
            if response.status_code == 200:
                try:
                    delta = response.output.choices[0].message.content
                    if delta:
                        yield delta
                except (AttributeError, IndexError, TypeError):
                    pass
            else:
                logger.warning("stream_chunk_failed", extra={"code": response.status_code})
                break
    except Exception as e:
        logger.error("stream_generation_error", extra={"error": str(e)})
        yield "生成过程发生错误，请稍后再试。"


# ── 文件名清洗工具 ────────────────────────────────────────────

_GENERIC_NAME_RE = re.compile(
    r'^(img|image|photo|dsc|pic|screenshot|scan|capture|frame|file|\d+|'
    r'img_\d+|dsc_\d+|photo_\d+)$',
    re.IGNORECASE,
)


def _friendly_filename(raw_filename: str, image_id) -> str:
    """将原始存储文件名转换为可读展示名称"""
    if not raw_filename:
        return f"文书 #{image_id}" if image_id else "未知文书"
    base = os.path.splitext(raw_filename)[0]
    clean = re.sub(r'_[0-9a-f]{8}$', '', base).strip()
    if not clean or _GENERIC_NAME_RE.fullmatch(clean):
        return f"文书 #{image_id}" if image_id else "未知文书"
    return clean


# ── Sources 构建（共享逻辑）──────────────────────────────────

def _build_sources(context_items: list) -> list:
    """将检索到的上下文条目转换为前端可展示的 sources 列表。"""
    sources = []
    for i, item in enumerate(context_items):
        meta = item.get("metadata", {})
        full_text = item.get("text", "")
        ocr_only = full_text.split("\n【时间】")[0].split("\n【卖方】")[0]
        excerpt = ocr_only[:80].strip() + ("..." if len(ocr_only) > 80 else "")
        image_id = meta.get("image_id", "")
        raw_filename = meta.get("filename", "")
        display_filename = _friendly_filename(raw_filename, image_id)
        sources.append(
            {
                "index": i + 1,
                "doc_id": meta.get("structured_result_id", meta.get("ocr_result_id", "")),
                "image_id": image_id,
                "filename": display_filename,
                "time": meta.get("time", ""),
                "location": meta.get("location", ""),
                "seller": meta.get("seller", ""),
                "buyer": meta.get("buyer", ""),
                "price": meta.get("price", ""),
                "subject": meta.get("subject", ""),
                "excerpt": excerpt,
            }
        )
    return sources


# ── RAG 主流程（非流式）──────────────────────────────────────

async def rag_pipeline(question: str, db: Session, history=None) -> dict:
    """
    RAG 主流程（非流式版本，保留向后兼容）。
    返回：{"answer": str, "sources": [...]}
    """
    try:
        q_vec = await get_text_embeddings(question)
        context_items = await retrieve_context(q_vec)
        answer = await generate_answer(question, context_items, history)
    except Exception as e:
        logger.error("rag_pipeline_error", extra={"error": str(e)})
        answer = "抱歉，处理您的问题时出现了意外错误，请稍后再试。"
        context_items = []

    return {"answer": answer, "sources": _build_sources(context_items)}


# 兼容旧调用
def index_document(doc_id: str, text: str, embedding: list) -> None:
    from app.services.vector_store.chroma import upsert_document
    upsert_document(doc_id=doc_id, text=text, embedding=embedding)
