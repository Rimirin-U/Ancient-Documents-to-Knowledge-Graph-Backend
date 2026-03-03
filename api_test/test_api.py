"""
API 测试脚本
测试所有的 FastAPI 端点
"""

import requests
import json
import os
import time
from pathlib import Path

# API 基础地址
BASE_URL = "http://localhost:8000"

# 测试数据
TEST_USERNAME = "testuser"
TEST_PASSWORD = "testpassword123"

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def print_test(message):
    print(f"{Colors.BLUE}[测试] {message}{Colors.END}")

def print_success(message):
    print(f"{Colors.GREEN}[成功] {message}{Colors.END}")

def print_error(message):
    print(f"{Colors.RED}[失败] {message}{Colors.END}")

def print_info(message):
    print(f"{Colors.YELLOW}[信息] {message}{Colors.END}")

# 全局变量存储 token 和 user_id
access_token = None
user_id = None

def test_root():
    """测试根端点"""
    print_test("测试 GET /api")
    try:
        response = requests.get(f"{BASE_URL}/api")
        if response.status_code == 200:
            print_success(f"根端点: {response.text}")
            return True
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_register():
    """测试注册"""
    global user_id
    print_test("测试 POST /register")
    try:
        payload = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
        response = requests.post(f"{BASE_URL}/register", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user_id = data.get("userId")
                print_success(f"注册成功 - 用户ID: {user_id}, 用户名: {data.get('username')}")
                return True
            else:
                # 用户可能已存在，这也是可以的
                print_info(f"用户可能已存在: {data.get('message')}")
                return True
        else:
            data = response.json()
            print_info(f"用户可能已存在: {data.get('detail', '未知错误')}")
            return True
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_login():
    """测试登录"""
    global access_token, user_id
    print_test("测试 POST /login")
    try:
        payload = {
            "username": TEST_USERNAME,
            "password": TEST_PASSWORD
        }
        response = requests.post(f"{BASE_URL}/login", json=payload)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                access_token = data.get("access_token")
                user_id = data.get("user_id")
                print_success(f"登录成功 - 用户ID: {user_id}")
                print_info(f"Token: {access_token[:20]}...")
                return True
            else:
                print_error(f"登录失败: {data.get('detail')}")
                return False
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_get_user_info():
    """测试获取用户信息"""
    print_test("测试 GET /user/info")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(f"{BASE_URL}/user/info", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                user_info = data.get("user", {})
                print_success(f"获取用户信息成功")
                print_info(f"用户ID: {user_info.get('id')}, 用户名: {user_info.get('username')}")
                return True
            else:
                print_error(f"获取失败: {data.get('detail')}")
                return False
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_upload():
    """测试上传图片"""
    print_test("测试 POST /api/upload")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    test_file_path = str(Path(__file__).parent / "test_img" / "test_img.jpg")
    try:
        with open(test_file_path, "rb") as f:
            files = {"image": ("test_img.jpg", f, "image/jpeg")}
            headers = {
                "Authorization": f"Bearer {access_token}"
            }
            data = {
                "user_id": user_id or 1
            }
            
            response = requests.post(
                f"{BASE_URL}/api/upload",
                files=files,
                data=data,
                headers=headers
            )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("success"):
                image_id = result.get("imageId")
                print_success(f"上传成功 - 图片ID: {image_id}")
                print_info(f"文件名: {result.get('filename')}, 文件大小: {result.get('fileSize')} bytes")
                return image_id
            else:
                print_error(f"上传失败: {result.get('message')}")
                return None
        else:
            print_error(f"状态码: {response.status_code}")
            return None
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return None

def test_get_pic(image_id):
    """测试获取图片"""
    print_test(f"测试 GET /api/pic/{image_id}")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    if not image_id:
        print_error("未提供有效的图片ID")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(f"{BASE_URL}/api/pic/{image_id}", headers=headers)
        
        if response.status_code == 200:
            print_success(f"获取图片成功 - 响应大小: {len(response.content)} bytes")
            return True
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_get_analysis(image_id):
    """测试获取分析结果"""
    print_test(f"测试 GET /api/analysis/{image_id}")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(f"{BASE_URL}/api/analysis/{image_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            print_success(f"获取分析成功")
            print_info(f"节点数: {len(data.get('nodes', []))}, 连接数: {len(data.get('links', []))}")
            print_info(f"描述: {data.get('txt')}")
            return True
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_get_user_images(user_id_param):
    """测试获取用户的图片列表"""
    print_test(f"测试 GET /api/user-images (user_id={user_id_param})")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    if not user_id_param:
        print_error("未提供有效的用户ID")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "user_id": user_id_param,
            "skip": 0,
            "limit": 10
        }
        response = requests.get(f"{BASE_URL}/api/user-images", headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                result_data = data.get("data", {})
                total = result_data.get("total", 0)
                ids = result_data.get("ids", [])
                print_success(f"获取用户图片列表成功")
                print_info(f"总数: {total}, 当前返回: {len(ids)} 个")
                if ids:
                    print_info(f"图片IDs: {ids}")
                return True, ids if ids else []
            else:
                print_error(f"获取失败: {data.get('detail')}")
                return False, []
        else:
            print_error(f"状态码: {response.status_code}")
            return False, []
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False, []

def test_get_ocr_results(image_id):
    """测试获取图片的OCR结果列表"""
    print_test(f"测试 GET /api/image-ocr-results/{image_id}")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    if not image_id:
        print_error("未提供有效的图片ID")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        params = {
            "skip": 0,
            "limit": 10
        }
        response = requests.get(f"{BASE_URL}/api/image-ocr-results/{image_id}", headers=headers, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                result_data = data.get("data", {})
                total = result_data.get("total", 0)
                ids = result_data.get("ids", [])
                print_success(f"获取图片的OCR结果列表成功")
                print_info(f"总数: {total}, 当前返回: {len(ids)} 个")
                if ids:
                    print_info(f"OCR结果IDs: {ids}")
                return True, ids if ids else []
            else:
                print_error(f"获取失败: {data.get('detail')}")
                return False, []
        else:
            print_error(f"状态码: {response.status_code}")
            return False, []
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False, []

def test_get_ocr_result(ocr_id):
    """测试获取指定ID的OCR结果"""
    print_test(f"测试 GET /api/ocr/{ocr_id}")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    if not ocr_id:
        print_error("未提供有效的OCR结果ID")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.get(f"{BASE_URL}/api/ocr/{ocr_id}", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                ocr_data = data.get("data", {})
                print_success(f"获取OCR结果成功")
                print_info(f"OCR ID: {ocr_data.get('id')}, 图片ID: {ocr_data.get('image_id')}")
                text_preview = ocr_data.get('raw_text', '')[:50]
                print_info(f"识别文本预览: {text_preview}...")
                return True
            else:
                print_error(f"获取失败: {data.get('detail')}")
                return False
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_logout():
    """测试退出登录"""
    print_test("测试 POST /logout")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.post(f"{BASE_URL}/logout", headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("success"):
                print_success(f"退出登录成功")
                return True
            else:
                print_error(f"退出失败: {data.get('message')}")
                return False
        else:
            print_error(f"状态码: {response.status_code}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_perform_image_ocr(image_id):
    """测试执行图片OCR"""
    print_test(f"测试 POST /api/image-ocr/{image_id}")
    if not access_token:
        print_error("未获取到有效的token")
        return False
    
    if not image_id:
        print_error("未提供有效的图片ID")
        return False
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        response = requests.post(f"{BASE_URL}/api/image-ocr/{image_id}", headers=headers)
        
        if response.status_code == 200:
            print_success(f"OCR 执行成功")
            return True
        else:
            print_error(f"状态码: {response.status_code}")
            print_error(f"响应: {response.text}")
            return False
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False

def test_wait_for_ocr_completion(image_id, timeout=60):
    """等待OCR结果完成，每2秒检查一次"""
    print_test(f"等待OCR结果完成 (image_id={image_id})")
    if not access_token:
        print_error("未获取到有效的token")
        return False, None
    
    if not image_id:
        print_error("未提供有效的图片ID")
        return False, None
    
    try:
        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # 首先获取OCR结果列表
        start_time = time.time()
        ocr_result_id = None
        
        # 循环等待直到找到OCR结果或超时
        while time.time() - start_time < timeout:
            try:
                params = {
                    "skip": 0,
                    "limit": 10
                }
                response = requests.get(
                    f"{BASE_URL}/api/image-ocr-results/{image_id}",
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        result_data = data.get("data", {})
                        ids = result_data.get("ids", [])
                        if ids:
                            ocr_result_id = ids[0]
                            print_success(f"找到OCR结果 ID: {ocr_result_id}")
                            break
            except Exception as e:
                print_info(f"获取OCR结果列表失败: {str(e)}")
            
            time.sleep(2)
        
        if not ocr_result_id:
            print_error(f"在{timeout}秒内未找到OCR结果")
            return False, None
        
        # 现在轮询检查OCR结果状态，直到完成或失败
        print_info("开始轮询OCR结果状态...")
        poll_start_time = time.time()
        
        while time.time() - poll_start_time < timeout:
            try:
                response = requests.get(
                    f"{BASE_URL}/api/ocr/{ocr_result_id}",
                    headers=headers
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        ocr_data = data.get("data", {})
                        status = ocr_data.get("status")
                        
                        print_info(f"OCR 状态: {status}")
                        
                        if status == "done":
                            text_preview = ocr_data.get('raw_text', '')[:100]
                            print_success(f"OCR 完成! 识别文本预览: {text_preview}...")
                            return True, ocr_result_id
                        elif status == "failed":
                            print_error(f"OCR 失败")
                            return False, ocr_result_id
                        # 其他状态(pending, processing)继续轮询
            except Exception as e:
                print_info(f"获取OCR结果详情失败: {str(e)}")
            
            time.sleep(2)
        
        print_error(f"轮询超时，OCR未完成")
        return False, ocr_result_id
        
    except Exception as e:
        print_error(f"请求失败: {str(e)}")
        return False, None

def main():
    """运行所有测试"""
    print(f"\n{Colors.BLUE}{'='*60}")
    print("FastAPI 应用程序测试脚本")
    print(f"{'='*60}{Colors.END}\n")
    
    print_info(f"API 基础地址: {BASE_URL}")
    print_info(f"测试用户: {TEST_USERNAME}\n")
    
    results = {
        "根端点": test_root(),
        "注册": test_register(),
        "登录": test_login(),
        "获取用户信息": test_get_user_info(),
    }
    
    # 上传图片并获取ID
    image_id = test_upload()
    results["上传图片"] = image_id is not None
    
    # 如果上传成功，测试获取图片和分析
    if image_id:
        results["获取图片"] = test_get_pic(image_id)
        results["获取分析"] = test_get_analysis(image_id)
        # 测试获取用户的图片列表
        success, image_ids = test_get_user_images(user_id)
        results["获取用户图片列表"] = success
        
        if image_ids and len(image_ids) > 0:
            # 使用获取到的第一个图片ID执行OCR
            test_image_id = image_ids[0]
            print_info(f"使用图片ID {test_image_id} 执行OCR测试")
            
            # 执行OCR
            ocr_executed = test_perform_image_ocr(test_image_id)
            results["执行OCR"] = ocr_executed
            
            if ocr_executed:
                # 等待OCR完成
                success, ocr_result_id = test_wait_for_ocr_completion(test_image_id)
                results["等待OCR完成"] = success
            else:
                results["等待OCR完成"] = False
        else:
            print_error("未获取到用户的图片列表，无法执行OCR测试")
            results["执行OCR"] = False
            results["等待OCR完成"] = False
    else:
        results["获取图片"] = False
        results["获取分析"] = False
        results["获取用户图片列表"] = False
        results["执行OCR"] = False
        results["等待OCR完成"] = False
    
    results["退出登录"] = test_logout()
    
    # 打印测试总结
    print(f"\n{Colors.BLUE}{'='*60}")
    print("测试总结")
    print(f"{'='*60}{Colors.END}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}✓ 通过{Colors.END}" if result else f"{Colors.RED}✗ 失败{Colors.END}"
        print(f"{test_name}: {status}")
    
    print(f"\n总体: {Colors.GREEN if passed == total else Colors.YELLOW}{passed}/{total} 个测试通过{Colors.END}\n")

if __name__ == "__main__":
    main()
