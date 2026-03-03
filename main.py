
import os
import shutil
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from database import init_db, get_db, Image, User, OcrResult
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
import jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from ocr import ocr_image_by_id

# JWT 配置
SECRET_KEY = "temp"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60 # 24h

# 密码加密
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# HTTP Bearer scheme
security = HTTPBearer()

app = FastAPI()

# Pydantic 模型
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    created_at: datetime

# 工具函数
def hash_password(password: str) -> str:
    """加密密码"""
    return pwd_context.hash(password[:72])

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password[:72], hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> dict:
    """验证JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token无效")

# 在应用启动时初始化数据库
init_db()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 存储
UPLOAD_DIR = "pic"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

# 路由

# POST /register - 注册
@app.post("/register")
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    # 检查用户是否已存在
    existing_user = db.query(User).filter(User.username == request.username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # 创建新用户
    hashed_password = hash_password(request.password)
    db_user = User(
        username=request.username,
        password_hash=hashed_password,
        created_at=datetime.now(timezone.utc)
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return {
        "success": True,
        "message": "注册成功",
        "userId": db_user.id,
        "username": db_user.username
    }

# POST /login - 登录
@app.post("/login")
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    # 查询用户
    db_user = db.query(User).filter(User.username == request.username).first()
    if not db_user or not verify_password(request.password, db_user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    # 生成JWT token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": db_user.username, "user_id": db_user.id},
        expires_delta=access_token_expires
    )
    
    return {
        "success": True,
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "username": db_user.username
    }

# GET /user/info - 获取用户信息
@app.get("/user/info")
async def get_user_info(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    
    # 验证token
    payload = verify_token(token)
    username = payload.get("sub")
    
    # 查询用户
    db_user = db.query(User).filter(User.username == username).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    return {
        "success": True,
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "created_at": db_user.created_at.isoformat()
        }
    }

# POST /logout - 退出登录
@app.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    return {
        "success": True,
        "message": "logout ok"
    }

# GET
@app.get("/api")
async def read_root():
    return "Hello, World!"

# POST /api/upload
@app.post("/api/upload")
async def upload_image(
    image: UploadFile = File(...), 
    user_id: int = 1, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    # 允许的文件扩展名
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
    # 文件大小限制：10MB
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB   
    # 验证文件扩展名
    ext = os.path.splitext(image.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return {
            "success": False, 
            "message": f"不支持的文件类型。允许的类型: {', '.join(ALLOWED_EXTENSIONS)}"
        }
    
    # 读取文件数据并验证大小
    try:
        file_data = await image.read()
        file_size = len(file_data)
        
        # 验证文件大小
        if file_size > MAX_FILE_SIZE:
            return {
                "success": False,
                "message": f"文件过大。最大允许大小: 10MB, 当前大小: {file_size / 1024 / 1024:.2f}MB"
            }
        
        if file_size == 0:
            return {
                "success": False,
                "message": "文件为空"
            }
    except Exception as e:
        return {"success": False, "message": f"读取文件失败: {str(e)}"}
    # 生成唯一文件名
    original_name = os.path.splitext(image.filename or "upload")[0]
    unique_filename = f"{original_name}_{uuid.uuid4().hex[:8]}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    # 保存文件到磁盘
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_data)
    except Exception as e:
        return {"success": False, "message": f"保存文件失败: {str(e)}"}
    
    # 保存图片信息到数据库
    try:
        db_image = Image(
            user_id=user_id,
            filename=unique_filename,
            path=file_path,
            upload_time=datetime.now(timezone.utc)
        )
        db.add(db_image)
        db.commit()
        db.refresh(db_image)
        
        return {
            "success": True,
            "imageId": db_image.id,
            "filename": db_image.filename,
            "originalName": image.filename,
            "fileSize": file_size
        }
    except Exception as e:
        db.rollback()
        # 删除已保存的文件
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except:
            pass
        return {"success": False, "message": f"保存到数据库失败: {str(e)}"}

# GET /api/pic/{id}
@app.get("/api/pic/{id}")
async def get_pic(
    id: int, 
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    # 从数据库查询图片信息
    db_image = db.query(Image).filter(Image.id == id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")
    if not os.path.exists(str(db_image.path)):
        raise HTTPException(status_code=404, detail="image file not found")
    return FileResponse(str(db_image.path))

# GET /api/analysis/{id}
@app.get("/api/analysis/{id}")
async def get_analysis(
    id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    response_data = {
        "nodes": [
            {
                "id": id,
                "name": "劉永濟",
                "type": "person",
                "category": "立約人",
                "symbolSize": 40,
                "itemStyle": {
                    "color": "#5470c6",
                    "borderColor": "#fff",
                    "borderWidth": 2,
                    "shadowBlur": 10,
                    "shadowColor": "rgba(0, 0, 0, 0.3)"
                }
            },
            {
                "id": "file2_node1",
                "name": "白田四形",
                "type": "object",
                "category": "标的",
                "symbolSize": 35,
                "itemStyle": {
                    "color": "#91cc75",
                    "borderColor": "#fff",
                    "borderWidth": 2,
                    "shadowBlur": 10,
                    "shadowColor": "rgba(0, 0, 0, 0.3)"
                }
            }
        ],
        "links": [
            {
                "source": id,
                "target": "file2_node1",
                "value": "出让",
                "lineStyle": {
                    "color": "#ff0000",
                    "width": 2
                }
            }
        ],
        "categories": [
            {"name": "立約人"},
            {"name": "标的"}
        ],
        "txt": f"ID: {id} 的识别结果"
    }
    return response_data

# GET /api/ocr/{id}
@app.get("/api/ocr/{id}")
async def get_ocr_result(
    id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """获取指定id的OCR结果"""
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    # 查询OCR结果
    ocr_result = db.query(OcrResult).filter(OcrResult.id == id).first()
    
    if not ocr_result:
        raise HTTPException(status_code=404, detail="OCR结果不存在")
    
    return {
        "success": True,
        "data": {
            "id": ocr_result.id,
            "image_id": ocr_result.image_id,
            "raw_text": ocr_result.raw_text,
            "status": ocr_result.status.value,
            "created_at": ocr_result.created_at.isoformat()
        }
    }

# GET /api/user-images
@app.get("/api/user-images")
async def get_user_images(
    user_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """根据用户id 分页返回该用户对应的Image的id"""
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    # 验证用户存在
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    
    # 查询用户的图片，分页返回id
    images = db.query(Image.id).filter(Image.user_id == user_id).offset(skip).limit(limit).all()
    
    # 获取总数
    total = db.query(Image).filter(Image.user_id == user_id).count()
    
    return {
        "success": True,
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "ids": [image[0] for image in images]
        }
    }

# GET /api/image-ocr/{image_id}
@app.get("/api/image-ocr-results/{image_id}")
async def get_image_ocr_results(
    image_id: int,
    skip: int = 0,
    limit: int = 10,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """根据Image id 分页返回该Image对应的OcrResult的id"""
    # 验证token
    token = credentials.credentials
    verify_token(token)
    
    # 验证图片存在
    image = db.query(Image).filter(Image.id == image_id).first()
    if not image:
        raise HTTPException(status_code=404, detail="图片不存在")
    
    # 查询OCR结果，分页返回id
    ocr_results = db.query(OcrResult.id).filter(OcrResult.image_id == image_id).offset(skip).limit(limit).all()
    
    # 获取总数
    total = db.query(OcrResult).filter(OcrResult.image_id == image_id).count()
    
    return {
        "success": True,
        "data": {
            "total": total,
            "skip": skip,
            "limit": limit,
            "ids": [result[0] for result in ocr_results]
        }
    }

# POST /api/image-ocr/{image_id}
@app.post("/api/image-ocr/{image_id}")
async def perform_image_ocr(
    image_id: int,
    db: Session = Depends(get_db),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """根据Image id 执行OCR 结果保存在OcrResult表中"""
    # 验证token
    token = credentials.credentials
    verify_token(token)
    ocr_image_by_id(image_id, db)


if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=3000)