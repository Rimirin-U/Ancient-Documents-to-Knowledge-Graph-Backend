
# 欢迎来到我们的古籍知识图谱项目！

本项目是一个基于 FastAPI 的后端系统，旨在通过 OCR（光学字符识别）和知识抽取技术，将古代文书（如契约）转化为结构化的知识图谱数据。

## 核心功能

1.  **OCR 识别**：使用 PaddleOCR 识别古籍图片中的文字。
2.  **知识抽取**：利用大模型（Qwen）从文本中提取实体（人、地、时间）和关系。
3.  **智能增强**：
    *   **自动翻译**：将晦涩的古文契约翻译为现代汉语。
    *   **时间标准化**：自动将清代年号（如“光绪三年”）转换为公历年份。
4.  **图谱分析**：构建社会关系网络，分析乡村权力结构。

## Python 环境

`python 3.12.9`

## 安装依赖

```bash
pip install -r requirements.txt
```

## 启动服务器

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 3000
```

## API 测试

我们提供了自动化测试脚本，用于验证全流程（上传 -> OCR -> 抽取 -> 分析）：

```bash
python api_test/test_analysis_flow.py
```

## 目录结构

*   `app/`: 核心业务逻辑
    *   `core/`: 标准化与翻译模块
    *   `services/`: LLM 服务
*   `extract.py`: 知识抽取主逻辑
*   `analysis.py`: 图谱构建与分析
*   `ocr.py`: OCR 处理
*   `database.py`: 数据库模型
*   `main.py`: API 入口
