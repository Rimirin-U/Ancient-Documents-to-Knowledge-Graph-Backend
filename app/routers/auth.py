"""认证路由：注册 / 登录 / 登出 / Token 刷新"""
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import User, get_beijing_time, get_db
from app.core.config import settings
from app.core.logger import get_logger
from app.core.security import (
    create_access_token,
    hash_password,
    security,
    verify_password,
    verify_token,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["认证"])


class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")

    hashed_password = hash_password(request.password)
    db_user = User(
        username=request.username,
        email=request.email,
        password_hash=hashed_password,
        created_at=get_beijing_time(),
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    logger.info("user_registered", extra={"username": db_user.username, "user_id": db_user.id})

    return {
        "success": True,
        "message": "注册成功",
        "userId": db_user.id,
        "username": db_user.username,
        "email": db_user.email,
    }


@router.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == request.username).first()
    if not db_user or not verify_password(request.password, db_user.password_hash):
        logger.warning("login_failed", extra={"username": request.username})
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username, "user_id": db_user.id},
        expires_delta=access_token_expires,
    )

    logger.info("user_logged_in", extra={"username": db_user.username, "user_id": db_user.id})

    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "username": db_user.username,
    }


@router.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    verify_token(token)
    return {"success": True, "message": "logout ok"}


@router.post("/refresh")
async def refresh_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials
    payload = verify_token(token)
    username = payload.get("sub")

    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    new_access_token = create_access_token(
        data={"sub": db_user.username, "user_id": db_user.id},
        expires_delta=access_token_expires,
    )

    return {"success": True, "access_token": new_access_token, "token_type": "bearer"}
