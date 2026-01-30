import dashscope
from dashscope import Generation
import json
import re
import os

# === 从环境变量获取API Key===
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "sk-293d49ac3daf4fd58b643b1542a4c89f")


def _postprocess_entities(entities):
    cleaned_entities = []
    for ent in entities:
        # 自动补全日期role（图谱模块需要）
        if ent.get("type") == "date" and "role" not in ent:
            ent["role"] = "日期"

        if ent.get("role") == "标的":
            value = ent["value"]
            # 如果长度合理且无明显乱码，保留原值
            if len(value) <= 15 and not re.search(r"[卍\x00-\x1f]|[^\u4e00-\u9fa5\d\s\.\u3000-\u303f\uff00-\uffef]",
                                                  value):
                cleaned_entities.append(ent)
                continue

            # 优化单位匹配：包含"厘"（关键修复！）
            patterns = [
                r"(田|地|屋|房|水田|旱地|宅基地)[^，。；]*?([一二三四五六七八九十百千\d]+[分亩间所块处厘])",
                r"([^，。；]*?(?:田|地|屋|房)[^，。；]*?)",  # 退化方案
            ]
            extracted = None
            for pattern in patterns:
                match = re.search(pattern, value)
                if match:
                    extracted = match.group(0).strip()
                    break

            if extracted and len(extracted) >= 2:
                ent["value"] = extracted
            else:
                ent["value"] = value[:20] + "..." if len(value) > 20 else value
            cleaned_entities.append(ent)
        else:
            cleaned_entities.append(ent)
    return cleaned_entities


def extract_entities_relations_with_qwen(text: str, model="qwen-turbo"):
    """
    优化版：确保日期role + 单位匹配（包含"厘"）
    """
    prompt = f"""
你是一位精通中国古代契约文书的专家。请从以下文本中精确提取结构化信息。

【实体要求】
- 立约人：通常是“立契人”“立约人”“永賣田約人”后的姓名
- 标的：被出让的物品（如“水田三亩”“房屋一所”）。若描述过长或含乱码，请尽量简化为核心部分（如“田三亩”）。
- 日期：立契时间（保留原文格式，如“道光十二年二月初二”）

【关系要求】
- 出让：立约人 → 标的
- 见证：每位明确提到的见证人（如“中人XXX”“见证人XXX”） → 本契

【输出规则】
1. 仅输出一个合法 JSON 对象，不要任何解释、Markdown、注释或额外文字。
2. 若字段不确定，请留空（不要编造）。
3. 严格使用以下格式：

{{
  "entities": [
    {{"type": "person", "value": "张三", "role": "立约人"}},
    {{"type": "object", "value": "水田三亩", "role": "标的"}},
    {{"type": "date", "value": "道光十二年二月初二"}}
  ],
  "relations": [
    {{"subject": "张三", "predicate": "出让", "object": "水田三亩"}},
    {{"subject": "李四", "predicate": "见证", "object": "本契"}}
  ]
}}

【契约文本】
{text}

【JSON 输出】
"""

    try:
        response = Generation.call(
            model=model,
            prompt=prompt,
            temperature=0.05,
            result_format="text",
            max_tokens=512
        )
        raw_output = response.output.text.strip() # type: ignore

        # 尝试多种方式提取 JSON
        json_str = None
        match = re.search(r"```json\s*(\{.*?\})\s*```", raw_output, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            match = re.search(r"\{.*\}", raw_output, re.DOTALL)
            if match:
                json_str = match.group(0)

        if json_str:
            # 修复常见 JSON 错误
            json_str = json_str.replace("'", '"')
            json_str = re.sub(r',\s*([\}\]])', r'\1', json_str)
            try:
                result = json.loads(json_str)
                # 应用后处理（含日期role补全）
                if "entities" in result:
                    result["entities"] = _postprocess_entities(result["entities"])
                return result
            except json.JSONDecodeError as e:
                print(f"[JSON Decode Error] {e}")

        return {"entities": [], "relations": []}

    except Exception as e:
        print(f"[Qwen API ERROR] {e}")
        return {"entities": [], "relations": []}


# === 从文件读取契约文本 ===
def read_contract_text(file_path: str) -> str:
    encodings = ['utf-8', 'gbk', 'gb2312', 'latin1']
    for enc in encodings:
        try:
            with open(file_path, 'r', encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    raise ValueError(f"无法以常见编码读取文件: {file_path}")


def process_contract_by_id(id: str, model="qwen-turbo") -> bool:
    """
    输入 id
    读取 ./output/text/{id}.txt
    输出 ./output/extract/{id}.txt
    成功返回 True，失败返回 False
    """
    try:
        input_path = f"./output/text/{id}.txt"
        output_dir = "./output/extract"
        output_path = f"{output_dir}/{id}.txt"

        os.makedirs(output_dir, exist_ok=True)

        contract_text = read_contract_text(input_path)
        result = extract_entities_relations_with_qwen(contract_text, model=model)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return True

    except Exception as e:
        print(f"[处理失败][ID={id}] {e}")
        return False