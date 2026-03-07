# 部署文档 (Deployment Guide)

## 1. 环境要求
- **操作系统**: Windows / Linux / macOS
- **Python 版本**: 3.8+
- **数据库**: SQLite (默认) 或 PostgreSQL/MySQL

## 2. 安装依赖
在 `Ancient-Documents-to-Knowledge-Graph-Backend` 目录下执行：
```bash
pip install -r requirements.txt
```

**注意**: 如果你在 Windows 上遇到 `paddleocr` 安装问题，请确保已安装 Microsoft Visual C++ Build Tools。

## 3. 配置环境变量
复制 `.env.example` (如果存在) 为 `.env`，或直接创建 `.env` 文件，包含以下内容：
```ini
SECRET_KEY=your_secure_secret_key_here
ALGORITHM=HS256
DASHSCOPE_API_KEY=your_dashscope_api_key  # 可选，用于通义千问大模型
```

## 4. 启动服务
### 开发模式
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

### 生产模式
```bash
uvicorn main:app --host 0.0.0.0 --port 3000 --workers 4
```

## 5. 前端适配说明
本项目后端已启用**适配器模式**，支持前端应用直接调用。
- **上传接口**: `POST /api/upload` (无需鉴权，自动触发全流程分析)
- **查询接口**: `GET /api/analysis/{id}` (无需鉴权，返回聚合结果)

请确保前端代码 (`app/detail.tsx` 等) 中的 API 地址配置正确：
```javascript
// 示例：将 IP 替换为你电脑的局域网 IP
const API_URL = "http://192.168.1.100:3000"; 
```

## 6. 常见问题
- **Q: 上传后一直显示“正在分析”？**
  - A: 检查后端控制台是否有报错。OCR 和大模型分析可能需要较长时间（10-30秒），请耐心等待。
- **Q: 提示 "ImportError: DLL load failed"？**
  - A: 通常是 `paddleocr` 或 `opencv` 的依赖缺失。尝试安装 `opencv-python-headless`。
