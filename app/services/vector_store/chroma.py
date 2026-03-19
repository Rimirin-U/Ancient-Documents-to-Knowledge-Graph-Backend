"""
ChromaDB 向量存储封装（含元数据支持）
持久化路径由 settings.UPLOAD_DIR/chromadb 决定，重启后数据不丢失
"""
import os
import chromadb
from app.core.config import settings


_client = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        persist_directory = os.path.join(settings.UPLOAD_DIR, "chromadb")
        os.makedirs(persist_directory, exist_ok=True)
        _client = chromadb.PersistentClient(path=persist_directory)
    return _client


def get_collection(name: str = "ancient_docs") -> chromadb.Collection:
    client = get_chroma_client()
    return client.get_or_create_collection(name=name)


def upsert_document(
    doc_id: str,
    text: str,
    embedding: list,
    metadata: dict | None = None,
) -> None:
    """
    向集合中插入或更新一条文档。
    metadata 应包含 filename、structured_result_id 等便于前端溯源的字段。
    """
    collection = get_collection()
    collection.upsert(
        documents=[text],
        embeddings=[embedding],
        ids=[doc_id],
        metadatas=[metadata or {}],
    )


def query_documents(
    query_embedding: list,
    top_k: int = 3,
) -> list[dict]:
    """
    向量检索，返回列表，每条包含 text、metadata 和 distance。
    集合为空或出错时返回空列表。
    """
    try:
        collection = get_collection()
        count = collection.count()
        if count == 0:
            return []

        actual_top_k = min(top_k, count)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=actual_top_k,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return [
            {
                "text": doc,
                "metadata": meta or {},
                "distance": dist,
            }
            for doc, meta, dist in zip(docs, metas, distances)
        ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning("chroma_query_error: %s", e)
        return []
