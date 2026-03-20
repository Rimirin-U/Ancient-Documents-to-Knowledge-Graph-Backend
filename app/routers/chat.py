"""RAG 智能问答路由"""
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import OcrResult, OcrStatus, StructuredResult, get_db
from app.core.logger import get_logger
from app.core.security import security, verify_token

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["智能问答"])


class HistoryTurn(BaseModel):
    role: str     # "user" | "assistant"
    content: str


class ChatQueryRequest(BaseModel):
    question: str
    history: Optional[List[HistoryTurn]] = None  # 近期对话历史（多轮对话支持）


@router.post(
    "/query",
    summary="RAG 智能问答",
    description=(
        "基于知识库（所有已 OCR 的文书）进行向量检索增强生成（RAG）问答。"
        "支持多轮对话（传入 history）、引用溯源（返回 sources）。"
    ),
)
async def chat_query(
    request: ChatQueryRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")

    from app.services.rag_service import rag_pipeline

    history = (
        [{"role": h.role, "content": h.content} for h in request.history]
        if request.history else None
    )
    logger.info("chat_query", extra={"user_id": user_id, "question_len": len(request.question)})

    try:
        result = await rag_pipeline(request.question, db, history)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("chat_query_error", extra={"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/kb-status",
    summary="知识库状态",
    description="返回当前知识库中已索引的文档数量。",
)
async def kb_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    verify_token(credentials.credentials)
    try:
        from app.services.vector_store.chroma import get_collection
        count = get_collection().count()
        return {"success": True, "data": {"indexed_count": count}}
    except Exception as e:
        return {"success": True, "data": {"indexed_count": 0}}


def _reindex_all_sync(db: Session):
    """
    遍历所有 OCR 完成的文档，将未索引或需要更新的文档写入 ChromaDB。
    - 有结构化结果的用富文本（OCR + 结构化字段）
    - 仅有 OCR 的用纯 OCR 文本
    返回操作统计。
    """
    from app.services.rag_service import _get_text_embeddings_sync
    from app.services.vector_store.chroma import upsert_document

    ocr_results = db.query(OcrResult).filter(OcrResult.status == OcrStatus.DONE).all()
    indexed, skipped = 0, 0
    _EMPTY = {"未识别", "未记载", "None", "null", ""}

    for ocr in ocr_results:
        if not ocr.raw_text:
            skipped += 1
            continue
        try:
            # 找最新的结构化结果
            struct = (
                db.query(StructuredResult)
                .filter(
                    StructuredResult.ocr_result_id == ocr.id,
                    StructuredResult.status == OcrStatus.DONE,
                )
                .order_by(StructuredResult.id.desc())
                .first()
            )

            metadata: dict = {
                "ocr_result_id": ocr.id,
                "image_id": ocr.image_id,
                "filename": ocr.image.filename if ocr.image else "",
                "structured_result_id": "",
                "time": "", "location": "", "seller": "",
                "buyer": "", "price": "", "subject": "",
            }
            rich_text = ocr.raw_text

            if struct and struct.content:
                import json as _json
                try:
                    sd = _json.loads(struct.content)
                except Exception:
                    sd = {}
                def _f(k: str) -> str:
                    v = str(sd.get(k, "")).strip()
                    return v if v not in _EMPTY else ""

                metadata.update({
                    "structured_result_id": struct.id,
                    "filename": sd.get("filename", metadata["filename"]),
                    "time": _f("Time"), "location": _f("Location"),
                    "seller": _f("Seller"), "buyer": _f("Buyer"),
                    "price": _f("Price"), "subject": _f("Subject"),
                })
                tags = [(k, metadata[k]) for k in
                        ("time", "location", "seller", "buyer", "price", "subject")
                        if metadata[k]]
                if tags:
                    tag_str = "　".join(f"【{label_map[k]}】{v}" for k, v in tags)
                    rich_text = ocr.raw_text + "\n" + tag_str

            embedding = _get_text_embeddings_sync(rich_text)
            upsert_document(
                doc_id=f"ocr_{ocr.id}",
                text=rich_text,
                embedding=embedding,
                metadata=metadata,
            )
            indexed += 1
        except Exception as e:
            logger.warning("reindex_doc_failed", extra={"ocr_id": ocr.id, "error": str(e)})
            skipped += 1

    return {"total": len(ocr_results), "indexed": indexed, "skipped": skipped}


label_map = {
    "time": "时间", "location": "地点", "seller": "卖方",
    "buyer": "买方", "price": "价格", "subject": "标的",
}


@router.post(
    "/reindex",
    summary="重建知识库索引",
    description=(
        "将所有 OCR 识别完成的文书重新写入向量数据库。"
        "适用于首次部署、手动补全历史数据，或 ChromaDB 数据丢失后的恢复。"
        "操作在后台异步执行，接口立即返回。"
    ),
)
async def reindex(
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    verify_token(credentials.credentials)
    # 在后台执行，避免阻塞请求
    background_tasks.add_task(_reindex_all_sync, db)
    logger.info("reindex_triggered")
    return {
        "success": True,
        "message": "知识库重建已在后台启动，所有已识别文书将陆续写入，请稍后刷新知识库状态。",
    }
