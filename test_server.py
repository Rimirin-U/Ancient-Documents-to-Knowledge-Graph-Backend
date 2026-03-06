
import os
import io
import time
import json
from fastapi.testclient import TestClient
from PIL import Image as PILImage

# 导入应用
from main import app
from database import init_db, SessionLocal, Base, engine

# 初始化数据库
init_db()

client = TestClient(app)

def create_dummy_image():
    """创建一个测试用的图片文件"""
    img = PILImage.new('RGB', (100, 30), color = (73, 109, 137))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def test_full_workflow():
    print("=== 开始全流程测试 ===")
    
    # 1. 注册
    print("\n1. 测试注册...")
    username = f"test_user_{int(time.time())}"
    password = "password123"
    response = client.post("/api/v1/auth/register", json={"username": username, "password": password})
    assert response.status_code == 200
    print("   注册成功")

    # 2. 登录
    print("\n2. 测试登录...")
    response = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   登录成功，获取Token")

    # 3. 上传图片
    print("\n3. 测试上传图片...")
    img_bytes = create_dummy_image()
    files = {"image": ("test.jpg", img_bytes, "image/jpeg")}
    response = client.post("/api/v1/images/upload", files=files, headers=headers)
    assert response.status_code == 200
    image_id = response.json()["imageId"]
    print(f"   上传成功，图片ID: {image_id}")

    # 4. OCR识别
    print("\n4. 测试OCR识别...")
    response = client.post(f"/api/v1/images/{image_id}/ocr", headers=headers)
    assert response.status_code == 200
    print("   OCR任务已提交")
    
    # 获取OCR结果
    ocr_result_id = None
    max_retries = 5
    for i in range(max_retries):
        print(f"   等待OCR完成... ({i+1}/{max_retries})")
        time.sleep(2) # 模拟等待
        response = client.get(f"/api/v1/images/{image_id}/ocr-results", headers=headers)
        data = response.json()
        if data["data"]["ids"]:
            ocr_result_id = data["data"]["ids"][0]
            # 检查状态
            res = client.get(f"/api/v1/ocr-results/{ocr_result_id}", headers=headers)
            if res.json()["data"]["status"] in ["done", "failed"]:
                break
    
    assert ocr_result_id is not None
    print(f"   OCR完成，结果ID: {ocr_result_id}")

    # 5. 结构化分析
    print("\n5. 测试结构化分析...")
    response = client.post("/api/v1/structured-results", json={"ocr_result_id": ocr_result_id}, headers=headers)
    assert response.status_code == 200
    print("   结构化分析任务已提交")
    
    structured_result_id = None
    for i in range(max_retries):
        print(f"   等待结构化分析完成... ({i+1}/{max_retries})")
        time.sleep(2)
        response = client.get(f"/api/v1/ocr-results/{ocr_result_id}/structured-results", headers=headers)
        data = response.json()
        if data["data"]["ids"]:
            structured_result_id = data["data"]["ids"][0]
            break
            
    assert structured_result_id is not None
    print(f"   结构化分析完成，结果ID: {structured_result_id}")

    # 6. 关系图分析
    print("\n6. 测试关系图分析...")
    response = client.post("/api/v1/relation-graphs", json={"structured_result_id": structured_result_id}, headers=headers)
    assert response.status_code == 200
    print("   关系图分析任务已提交")
    
    relation_graph_id = None
    for i in range(max_retries):
        print(f"   等待关系图分析完成... ({i+1}/{max_retries})")
        time.sleep(2)
        response = client.get(f"/api/v1/structured-results/{structured_result_id}/relation-graphs", headers=headers)
        data = response.json()
        if data["data"]["ids"]:
            relation_graph_id = data["data"]["ids"][0]
            break
            
    assert relation_graph_id is not None
    print(f"   关系图分析完成，结果ID: {relation_graph_id}")

    # 7. 跨文档分析
    print("\n7. 测试跨文档分析...")
    # 创建多任务
    response = client.post("/api/v1/multi-tasks", json={"structured_result_ids": [structured_result_id]}, headers=headers)
    assert response.status_code == 200
    multi_task_id = response.json()["multi_task_id"]
    print(f"   多任务创建成功，任务ID: {multi_task_id}")
    
    # 提交分析
    response = client.post("/api/v1/multi-relation-graphs", json={"multi_task_id": multi_task_id}, headers=headers)
    assert response.status_code == 200
    print("   跨文档分析任务已提交")
    
    multi_relation_graph_id = None
    for i in range(max_retries):
        print(f"   等待跨文档分析完成... ({i+1}/{max_retries})")
        time.sleep(2)
        response = client.get(f"/api/v1/multi-tasks/{multi_task_id}/multi-relation-graphs", headers=headers)
        data = response.json()
        if data["data"]["ids"]:
            multi_relation_graph_id = data["data"]["ids"][0]
            break
            
    assert multi_relation_graph_id is not None
    print(f"   跨文档分析完成，结果ID: {multi_relation_graph_id}")

    print("\n=== 所有测试通过！ ===")

if __name__ == "__main__":
    try:
        test_full_workflow()
    except Exception as e:
        print(f"\n❌ 测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
