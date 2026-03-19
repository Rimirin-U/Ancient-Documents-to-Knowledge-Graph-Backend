
import json
import os
import dashscope
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import StructuredResult
from app.core.config import settings
from fastapi.concurrency import run_in_threadpool

# RAG 配置
if settings.DASHSCOPE_API_KEY:
    dashscope.api_key = settings.DASHSCOPE_API_KEY

def _get_text_embeddings_sync(text: str):
    """调用 DashScope 获取文本向量 (Sync)"""
    if not settings.DASHSCOPE_API_KEY:
        # 模拟向量
        return [0.1] * 1536
        
    try:
        resp = dashscope.TextEmbedding.call(
            model=dashscope.TextEmbedding.Models.text_embedding_v1,
            input=text
        )
        if resp.status_code == 200:
            return resp.output['embeddings'][0]['embedding']
        else:
            print(f"Embedding failed: {resp}")
            return [0.1] * 1536
    except Exception as e:
        print(f"Embedding error: {e}")
        return [0.1] * 1536

async def get_text_embeddings(text: str):
    return await run_in_threadpool(_get_text_embeddings_sync, text)

def cosine_similarity(vec1, vec2):
    """计算余弦相似度"""
    import math
    dot_product = sum(a*b for a,b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a*a for a in vec1))
    norm_b = math.sqrt(sum(b*b for b in vec2))
    return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0

from app.services.vector_store.chroma import get_collection

async def retrieve_context(question_vec, db: Session, top_k=3):
    """
    使用 ChromaDB 进行向量检索
    """
    try:
        collection = get_collection()

        # 集合为空时直接返回，避免 ChromaDB 抛异常
        count = collection.count()
        if count == 0:
            return []

        # n_results 不能超过集合中实际文档数
        actual_top_k = min(top_k, count)

        results = collection.query(
            query_embeddings=[question_vec],
            n_results=actual_top_k
        )

        if results['documents'] and results['documents'][0]:
            return results['documents'][0]
    except Exception as e:
        print(f"ChromaDB retrieve error: {e}")

    return []

def index_document(doc_id: str, text: str, embedding: list):
    """
    将文档索引到 ChromaDB（upsert 避免重复 ID 报错）
    """
    collection = get_collection()
    collection.upsert(
        documents=[text],
        embeddings=[embedding],
        ids=[doc_id]
    )


def _generate_answer_sync(question: str, context_list: list):
    """调用 LLM 生成回答 (Sync)"""
    if not settings.DASHSCOPE_API_KEY:
        return "未配置 DASHSCOPE_API_KEY，无法生成智能回答。请联系管理员配置 API Key。"

    if not context_list:
        context_hint = "（知识库中暂无相关文档，将根据通用知识作答）"
        context_str = ""
    else:
        context_hint = ""
        context_str = "\n".join([f"- {c}" for c in context_list])

    messages = [
        {
            "role": "system",
            "content": (
                "你是一个专业的古籍研究助手。请根据提供的参考资料回答用户问题。"
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
            result_format='message'
        )
        if response.status_code == 200:
            # 兼容属性访问和字典访问两种 dashscope 版本
            try:
                return response.output.choices[0].message.content
            except (AttributeError, IndexError, TypeError):
                return response.output['choices'][0]['message']['content']
        else:
            print(f"LLM generation failed: {response.code} - {response.message}")
            return f"生成回答失败（{response.code}），请稍后再试。"
    except Exception as e:
        print(f"LLM generation error: {e}")
        return "生成过程发生错误，请稍后再试。"

async def generate_answer(question: str, context_list: list):
    return await run_in_threadpool(_generate_answer_sync, question, context_list)

async def rag_pipeline(question: str, db: Session):
    """RAG 主流程"""
    try:
        # 1. 问题向量化
        q_vec = await get_text_embeddings(question)

        # 2. 检索相关文档（空库或异常时返回空列表，不中断流程）
        context = await retrieve_context(q_vec, db)

        # 3. 生成回答
        answer = await generate_answer(question, context)
    except Exception as e:
        print(f"RAG pipeline unexpected error: {e}")
        answer = "抱歉，处理您的问题时出现了意外错误，请稍后再试。"
        context = []

    return {
        "answer": answer,
        "sources": context
    }
