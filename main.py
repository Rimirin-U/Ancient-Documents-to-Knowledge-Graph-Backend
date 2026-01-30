import os
import time
import shutil
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI()

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
async def upload_image(image: UploadFile = File(...)):
    # 获取文件后缀
    ext = os.path.splitext(image.filename or "")[1]
    # 生成时间戳文件名
    analysis_id = str(int(time.time() * 1000))
    file_name = f"{analysis_id}{ext}"
    file_path = os.path.join(UPLOAD_DIR, file_name)
    # 保存文件到磁盘
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(image.file, buffer)
    except Exception as e:
        return {"success": False, "message": str(e)}
    return {
        "success": True,
        "analysisId": analysis_id
    }

# GET /api/pic/:id
@app.get("/api/pic/{id}")
async def get_pic(id: str):
    # 在目录下查找以 id 开头的文件
    files = os.listdir(UPLOAD_DIR)
    file_name = next((f for f in files if f.startswith(id)), None)
    if not file_name:
        raise HTTPException(status_code=404, detail="image not found")
    file_path = os.path.join(UPLOAD_DIR, file_name)
    return FileResponse(file_path)

# GET /api/analysis/:id
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