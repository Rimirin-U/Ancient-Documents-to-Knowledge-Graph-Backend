"""RAG 智能问答路由"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from app.core.logger import get_logger
from app.core.security import security, verify_token

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/chat", tags=["智能问答"])


class ChatQueryRequest(BaseModel):
    question: str


@router.post(
    "/query",
    summary="RAG 智能问答",
    description="基于已上传文书的向量检索增强生成（RAG）问答。返回答案及引用来源（文书文件名/时间/地点/摘要），支持跨文档联合检索",
)
async def chat_query(
    request: ChatQueryRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")

    from app.services.rag_service import rag_pipeline

    logger.info("chat_query", extra={"user_id": user_id, "question_len": len(request.question)})

    try:
        result = await rag_pipeline(request.question, db)
        return {"success": True, "data": result}
    except Exception as e:
        logger.error("chat_query_error", extra={"error": str(e), "user_id": user_id})
        raise HTTPException(status_code=500, detail=str(e))
