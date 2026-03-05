# 古籍地契解析与社会网络挖掘系统

本项目是一个基于 LLM (Large Language Model) 和图算法的数字人文分析工具，旨在从清代/民国地契的 OCR 文本中提取结构化信息，进行逻辑纠错、实体消解，并最终挖掘出乡村社会的隐性权力网络。

本系统包含三个核心模块：
1.  **LLM Parser (Module 1)**: 利用大模型（如 Qwen-Plus）进行单文档解析，支持 OCR 纠错、关键信息提取（时间、买卖双方、价格等）以及**全文白话文翻译**。
2.  **Entity Resolution (Module 2)**: 跨文档实体共指消解。利用时空与社交关系算法，判断不同契约中的“张三”是否为同一人，解决“同名同人”与“异名同人”问题。
3.  **Social Network Analysis (Module 3)**: 隐性权力网络挖掘。构建人物关系图谱，计算中心性指标，自动识别“乡绅”、“牙行”、“地主”等关键社会角色。

---

## 🚀 快速开始

### 1. 环境准备

本系统基于 Python 开发，推荐使用 Python 3.8+。

#### 1.1 安装依赖

在项目根目录下打开终端，运行以下命令安装所需库：

```bash
pip install -r requirements.txt
# 注意：如果运行时提示缺少 jinja2，请单独安装：
pip install jinja2
```

#### 1.2 配置 API Key

本项目使用 OpenAI 接口格式调用大模型（默认适配阿里云百炼 Qwen-Plus，也可配置为其他兼容接口）。

1.  复制 `.env.example` 文件并重命名为 `.env`。
2.  在 `.env` 文件中填入您的 API Key 和 Base URL：

```ini
# .env 文件内容示例
OPENAI_API_KEY=sk-您的密钥...
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

---

## 🛠️ 使用指南 (一键运行)

本项目提供了一个自动化流水线脚本，可一键完成从文本解析到图谱生成的全过程。

### 1. 准备数据
将您的地契 OCR 文本文件（`.txt` 格式）放入 `data/` 目录下。
*   示例文件已包含在 `data/` 中（如 `1.txt` 等）。

### 2. 运行系统
在终端中执行以下命令：

```bash
python run_pipeline.py
```

系统将依次执行以下步骤：
1.  **解析与翻译**：读取 `data/` 中的文本，调用 LLM 提取信息并翻译。
2.  **实体消解**：将解析结果存入数据库，并合并同一实体。
3.  **网络分析**：基于数据库构建社会网络，分析角色。

### 3. 查看结果
运行完成后，结果将保存在 `output/` 目录下：
*   **`parsed_deeds.json`**: 包含所有地契的结构化数据及**全文翻译**。
*   **`social_network_graph.json`**: 生成的社会网络图谱数据（ECharts 格式）。

---

## 🔧 分步运行指南 (高级)

如果您需要单独调试或运行某个模块，可以使用以下命令：

### 第一步：单文档解析 (Module 1)
读取 `data/` 文件，调用 LLM 进行处理。
```bash
python -m app.run_module1
```

### 第二步：实体共指消解 (Module 2)
读取 JSON 数据，进行实体合并并存入 SQLite 数据库 (`land_deeds.db`)。
```bash
python -m app.run_module2
```

### 第三步：社会网络挖掘 (Module 3)
分析数据库中的关系，生成图谱数据。
```bash
python -m app.run_module3
```

---

## 📂 文件结构说明

*   `run_pipeline.py`: **项目主入口**，一键运行所有模块。
*   `app/`: 核心代码目录
    *   `parser.py`: 解析器编排层，协调 LLM 提取与翻译。
    *   `services/llm_service.py`: 封装 OpenAI 接口调用（支持异步）。
    *   `core/`: 核心业务逻辑
        *   `prompts.py` & `prompts/`: Prompt 模板管理。
        *   `translator.py`: 专门的全文翻译模块。
        *   `validator.py`: 数据校验逻辑。
    *   `models/`: 数据库模型定义 (`Document`, `Entity`, `Relation`)。
    *   `resolution.py`: 实体消解算法实现。
    *   `analysis.py`: 图谱分析与角色推演算法。
    *   `run_module*.py`: 各个模块的独立执行脚本。
*   `data/`: 存放原始 OCR 文本文件（输入）。
*   `output/`: 存放运行结果（输出）。
*   `land_deeds.db`: 结构化数据库（SQLite）。
*   `.env`: 环境变量配置文件。

---

## 📊 结果可视化

生成的 `output/social_network_graph.json` 文件可直接用于前端 ECharts 组件渲染。

**图谱特征：**
*   **节点 (Node)**: 代表人物或机构（如“篋叙堂”）。
*   **大小 (Size)**: 基于中心性算法计算，反映人物影响力。
*   **连线 (Link)**: 代表人物在同一份契约中共同出现（共现关系）。
*   **分类 (Category)**: 系统自动推断的角色，如“普通百姓”、“职业中人”、“乡绅”等。
