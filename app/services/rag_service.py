"""
RAG 问答服务（含引用溯源）

流程：
  1. 问题向量化（DashScope TextEmbedding）
  2. ChromaDB 向量检索 top-3 相关文档（含元数据）
  3. DashScope Qwen-Turbo 生成回答
  4. 返回 answer + sources（每条含 doc_id / filename / excerpt / image_id）
"""
import json

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

async def retrieve_context(question_vec: list, top_k: int = 3) -> list[dict]:
    """
    使用 ChromaDB 进行向量检索。
    返回列表，每条含 text / metadata / distance。
    """
    from app.services.vector_store.chroma import query_documents
    return await run_in_threadpool(query_documents, question_vec, top_k)


# ── 生成回答 ──────────────────────────────────────────────────

def _generate_answer_sync(question: str, context_items: list[dict]) -> str:
    if not settings.DASHSCOPE_API_KEY:
        return "未配置 DASHSCOPE_API_KEY，无法生成智能回答。"

    if not context_items:
        context_hint = "（知识库中暂无相关文档，将根据通用知识作答）"
        context_str = ""
    else:
        context_hint = ""
        context_str = "\n".join(
            [f"- [{i+1}] {item['text']}" for i, item in enumerate(context_items)]
        )

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的古籍研究助手。请根据提供的参考资料回答用户问题，"
                "回答时标注引用来源编号如 [1]、[2] 等。"
                "如果参考资料为空或没有相关内容，请依据通用知识作答，并如实说明。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"{context_hint}"
                + (f"\n参考资料：\n{context_str}\n\n" if context_str else "\n")
                + f"问题：{question}"
            ),
        },
    ]

    try:
        response = dashscope.Generation.call(
            model="qwen-turbo",
            messages=messages,
            result_format="message",
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


async def generate_answer(question: str, context_items: list[dict]) -> str:
    return await run_in_threadpool(_generate_answer_sync, question, context_items)


# ── RAG 主流程 ────────────────────────────────────────────────

async def rag_pipeline(question: str, db: Session) -> dict:
    """
    RAG 主流程。
    返回：
      {
        "answer": str,
        "sources": [
          {
            "index": 1,
            "doc_id": "sr_5",
            "image_id": 3,
            "filename": "contract_abc.jpg",
            "time": "乾隆五年",
            "location": "山西省平遥县",
            "excerpt": "前20字摘要..."
          },
          ...
        ]
      }
    """
    try:
        q_vec = await get_text_embeddings(question)
        context_items = await retrieve_context(q_vec)
        answer = await generate_answer(question, context_items)
    except Exception as e:
        logger.error("rag_pipeline_error", extra={"error": str(e)})
        answer = "抱歉，处理您的问题时出现了意外错误，请稍后再试。"
        context_items = []

    sources = []
    for i, item in enumerate(context_items):
        meta = item.get("metadata", {})
        text = item.get("text", "")
        sources.append(
            {
                "index": i + 1,
                "doc_id": meta.get("structured_result_id", ""),
                "image_id": meta.get("image_id", ""),
                "filename": meta.get("filename", "未知文件"),
                "time": meta.get("time", ""),
                "location": meta.get("location", ""),
                "excerpt": text[:60] + ("..." if len(text) > 60 else ""),
            }
        )

    return {"answer": answer, "sources": sources}


# 兼容旧调用（analysis_service.py 中的 index_document 调用已迁移到 chroma.py，保留此函数供外部使用）
def index_document(doc_id: str, text: str, embedding: list) -> None:
    from app.services.vector_store.chroma import upsert_document
    upsert_document(doc_id=doc_id, text=text, embedding=embedding)
