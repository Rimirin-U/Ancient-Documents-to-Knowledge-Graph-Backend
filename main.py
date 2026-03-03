
import os
import shutil
import uuid
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from database import init_db, get_db, Image, ImageStatus
from sqlalchemy.orm import Session
from datetime import datetime, timezone
app = FastAPI()

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

# GET /api
@app.get("/api")
async def read_root():
    return "Hello, World!"


# POST /api/upload
@app.post("/api/upload")
async def upload_image(image: UploadFile = File(...), user_id: int = 1, db: Session = Depends(get_db)):
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
            upload_time=datetime.now(timezone.utc),
            status=ImageStatus.PENDING
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
async def get_pic(id: int, db: Session = Depends(get_db)):
    # 从数据库查询图片信息
    db_image = db.query(Image).filter(Image.id == id).first()
    if not db_image:
        raise HTTPException(status_code=404, detail="image not found")
    if not os.path.exists(str(db_image.path)):
        raise HTTPException(status_code=404, detail="image file not found")
    return FileResponse(str(db_image.path))

# GET /api/analysis/{id}
@app.get("/api/analysis/{id}")
async def get_analysis(id: str):
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

if __name__ == "__main__":
    import uvicorn
    # 启动服务
    uvicorn.run(app, host="0.0.0.0", port=3000)