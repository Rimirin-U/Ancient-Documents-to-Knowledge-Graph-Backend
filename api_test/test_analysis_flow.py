
import requests
import time
import os
from pathlib import Path

# API 基础地址
BASE_URL = "http://localhost:3000"

# 测试用户 (使用已存在的用户或新注册)
TEST_USERNAME = "test_analysis_user"
TEST_PASSWORD = "password123"

# 全局变量
access_token = None
user_id = None

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    YELLOW = '\033[93m'
    END = '\033[0m'

def print_info(msg): print(f"{Colors.BLUE}[INFO] {msg}{Colors.END}")
def print_success(msg): print(f"{Colors.GREEN}[SUCCESS] {msg}{Colors.END}")
def print_error(msg): print(f"{Colors.RED}[ERROR] {msg}{Colors.END}")

def login_or_register():
    global access_token, user_id
    
    # 1. Try Login
    print_info("尝试登录...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    
    if resp.status_code == 200 and resp.json().get("success"):
        data = resp.json()
        access_token = data["access_token"]
        user_id = data["user_id"]
        print_success(f"登录成功. UserID: {user_id}")
        return True
    
    # 2. If login fails, try Register
    print_info("登录失败，尝试注册...")
    resp = requests.post(f"{BASE_URL}/api/v1/auth/register", json={"username": TEST_USERNAME, "password": TEST_PASSWORD})
    
    if resp.status_code == 200 and resp.json().get("success"):
        print_success("注册成功，重新登录...")
        return login_or_register() # Recursive call to login after register
    
    print_error(f"无法登录或注册: {resp.text}")
    return False

def upload_image():
    print_info("上传测试图片...")
    # Find a test image
    img_path = Path(__file__).parent / "test_img" / "test_img.jpg"
    if not img_path.exists():
        print_error(f"测试图片不存在: {img_path}")
        return None

    headers = {"Authorization": f"Bearer {access_token}"}
    with open(img_path, "rb") as f:
        files = {"image": ("test_img.jpg", f, "image/jpeg")}
        resp = requests.post(f"{BASE_URL}/api/v1/images/upload", headers=headers, files=files, data={"user_id": user_id})
    
    if resp.status_code == 200 and resp.json().get("success"):
        image_id = resp.json().get("imageId")
        print_success(f"图片上传成功. ImageID: {image_id}")
        return image_id
    
    print_error(f"图片上传失败: {resp.text}")
    return None

def ensure_ocr_done(image_id):
    print_info(f"检查图片 {image_id} 的OCR状态...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 1. Trigger OCR (idempotent-ish, or just check if result exists)
    # Check existing results first
    resp = requests.get(f"{BASE_URL}/api/v1/images/{image_id}/ocr-results", headers=headers)
    if resp.status_code == 200:
        data = resp.json().get("data", {})
        if data.get("total", 0) > 0:
            # Check the status of the latest one
            ocr_id = data["ids"][-1] # Get latest
            resp_detail = requests.get(f"{BASE_URL}/api/v1/ocr-results/{ocr_id}", headers=headers)
            if resp_detail.json().get("data", {}).get("status") == "done":
                print_success("OCR 已完成")
                return True

    # 2. Trigger OCR if not done
    print_info("触发 OCR 任务...")
    requests.post(f"{BASE_URL}/api/v1/images/{image_id}/ocr", headers=headers)
    
    # 3. Poll
    for i in range(30): # Wait up to 60s
        time.sleep(2)
        resp = requests.get(f"{BASE_URL}/api/v1/images/{image_id}/ocr-results", headers=headers)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            if data.get("total", 0) > 0:
                ocr_id = data["ids"][-1]
                resp_detail = requests.get(f"{BASE_URL}/api/v1/ocr-results/{ocr_id}", headers=headers)
                status = resp_detail.json().get("data", {}).get("status")
                if status == "done":
                    print_success("OCR 完成")
                    return True
                elif status == "failed":
                    print_error("OCR 失败")
                    return False
        print_info(f"等待 OCR... ({i+1}/30)")
    
    print_error("OCR 等待超时")
    return False

def test_extraction(image_id):
    print_info(f"测试知识抽取 API (ImageID: {image_id})...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    start_time = time.time()
    resp = requests.post(f"{BASE_URL}/api/v1/analysis/{image_id}/extract", headers=headers)
    duration = time.time() - start_time
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            print_success(f"知识抽取成功 (耗时 {duration:.2f}s)")
            print_info(f"抽取结果预览: {str(data.get('extraction'))[:200]}...")
            print_info(f"翻译预览: {str(data.get('translation'))[:100]}...")
            print_info(f"标准化年份: {data.get('normalized_year')}")
            return True
    
    print_error(f"知识抽取失败: {resp.text}")
    return False

def test_graph_analysis():
    print_info("测试全库图谱分析 API...")
    headers = {"Authorization": f"Bearer {access_token}"}
    
    resp = requests.get(f"{BASE_URL}/api/v1/analysis/graph", headers=headers)
    
    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            graph_data = data.get("data", {})
            nodes = graph_data.get("series", [{}])[0].get("data", [])
            links = graph_data.get("series", [{}])[0].get("links", [])
            print_success(f"图谱分析成功. 节点数: {len(nodes)}, 边数: {len(links)}")
            return True

    print_error(f"图谱分析失败: {resp.text}")
    return False

def main():
    if not login_or_register(): return
    
    # Use existing image or upload new
    image_id = upload_image()
    if not image_id: return
    
    if not ensure_ocr_done(image_id): return
    
    if test_extraction(image_id):
        test_graph_analysis()

if __name__ == "__main__":
    main()
