"""
LLM 调用工具模块
封装 DashScope Qwen-Turbo 的结构化提取和历史洞察生成，供其他 service 模块调用。
"""
import json
import re
from typing import Any, Dict, List

from fastapi.concurrency import run_in_threadpool

from app.core.config import settings

try:
    import dashscope
    from dashscope import Generation
    if settings.DASHSCOPE_API_KEY:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False


# ── 结构化提取 ───────────────────────────────────────────────

_STRUCTURE_FALLBACK: Dict[str, Any] = {
    "Time": "未识别",
    "Time_AD": None,
    "Location": "未识别",
    "Seller": "未识别",
    "Buyer": "未识别",
    "Middleman": "未识别",
    "Price": "未识别",
    "Subject": "未识别",
    "Translation": "由于未配置有效的LLM API Key，无法生成翻译和精确提取。请配置DASHSCOPE_API_KEY环境变量。",
}


def call_structure_llm_sync(text: str) -> Dict[str, Any]:
    """调用 LLM 从地契 OCR 文本中提取结构化字段（同步）"""
    if HAS_DASHSCOPE and settings.DASHSCOPE_API_KEY:
        prompt = f"""
        你是一个专业的古籍文档分析专家。请分析以下地契文档的OCR识别结果，提取关键信息并以JSON格式返回。

        需要提取的字段如下：
        - Time: 契约签订时间（原文）
        - Time_AD: 契约签订时间（公元纪年，整数年份，如1832）
        - Location: 土地/房产位置
        - Seller: 卖方姓名
        - Buyer: 买方姓名
        - Middleman: 中人/见证人姓名
        - Price: 交易价格（包含单位）
        - Subject: 交易标的物（如田地面积、房屋等）
        - Translation: 文档的现代文翻译

        OCR文本内容：
        {text}

        请仅返回JSON字符串，不要包含markdown标记或其他无关内容。
        """
        try:
            response = Generation.call(
                model=Generation.Models.qwen_turbo,
                prompt=prompt,
                result_format="message",
            )
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                content = re.sub(r"^```json\s*", "", content)
                content = re.sub(r"\s*```$", "", content)
                return json.loads(content)
            print(f"LLM结构化提取失败: {response.code} - {response.message}")
        except Exception as e:
            print(f"LLM结构化提取异常: {e}")
    return _STRUCTURE_FALLBACK.copy()


async def call_structure_llm(text: str) -> Dict[str, Any]:
    """call_structure_llm_sync 的异步包装"""
    return await run_in_threadpool(call_structure_llm_sync, text)


# ── 历史洞察生成 ─────────────────────────────────────────────

def _build_insights_prompt(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
    """根据统计数据构造 LLM 分析提示词"""
    doc_count = statistics.get("doc_count", 0)
    time_range = statistics.get("time_range", {})
    unique_people = statistics.get("unique_people", 0)
    cross_role = statistics.get("cross_role_people", [])
    top_people = statistics.get("top_people", [])
    top_locations = statistics.get("top_locations", [])
    land_chain_count = statistics.get("land_chain_count", 0)

    time_str = (
        f"公元 {time_range['start']} 年 — {time_range['end']} 年（跨度 {time_range.get('span', 0)} 年）"
        if time_range.get("start") and time_range.get("end")
        else "时间信息不完整"
    )
    summaries = []
    for d in parsed_datas[:8]:
        seller = d.get("Seller", "")
        buyer = d.get("Buyer", "")
        if seller and buyer and all(v not in ["未识别", "未知", ""] for v in [seller, buyer]):
            loc = d.get("Location", "")
            price = d.get("Price", "")
            t = d.get("Time", "")
            parts = [f"{t}：" if t and t not in ["未识别", ""] else ""]
            parts.append(f"{seller} → {buyer}")
            if loc and loc not in ["未识别", ""]:
                parts.append(f"，地点：{loc}")
            if price and price not in ["未识别", ""]:
                parts.append(f"，价格：{price}")
            summaries.append("  - " + "".join(parts))

    cross_str = "、".join(cross_role[:5]) if cross_role else "无"
    top_people_str = (
        "、".join([f"{p['name']}（涉及 {p['doc_count']} 份文书）" for p in top_people[:3]])
        if top_people else "数据不足"
    )
    locations_str = "、".join([l["name"] for l in top_locations[:4]]) if top_locations else "未提取到"
    tx_block = "\n".join(summaries) if summaries else "  （未能提取有效交易摘要）"

    return f"""你是专业的历史文书研究专家，擅长分析中国古代地契的社会关系与经济史意义。
请根据以下跨文档分析结果，用150-250字撰写一段专业的历史学分析摘要。

【分析数据】
- 文书总量：{doc_count} 份地契
- 时间范围：{time_str}
- 涉及人物：{unique_people} 人
- 交易概况：
{tx_block}
- 角色切换人物（曾在不同文书中既作卖方又作买方）：{cross_str}
- 核心人物（出现次数最多）：{top_people_str}
- 主要交易地点：{locations_str}
- 有多次易手记录的地块数：{land_chain_count} 处

【分析要求】
请选择有数据支撑的角度进行分析，语言专业凝练，不臆测无据内容，不超过250字。"""


def _generate_fallback_insights(statistics: Dict[str, Any]) -> str:
    """LLM 不可用时生成模板化洞察文字"""
    doc_count = statistics.get("doc_count", 0)
    time_range = statistics.get("time_range", {})
    unique_people = statistics.get("unique_people", 0)
    cross_role = statistics.get("cross_role_people", [])
    top_people = statistics.get("top_people", [])
    land_chain_count = statistics.get("land_chain_count", 0)

    parts = [f"本次跨文档分析共涉及 {doc_count} 份地契文书，"]
    if time_range.get("start") and time_range.get("end"):
        parts.append(
            f"时间跨度从公元 {time_range['start']} 年至 {time_range['end']} 年"
            f"（历时约 {time_range.get('span', 0)} 年），"
        )
    parts.append(f"共涉及 {unique_people} 位历史人物。")
    if cross_role:
        names = "、".join(cross_role[:3])
        parts.append(
            f"其中 {len(cross_role)} 人曾在不同文书中兼任多重角色（包括：{names} 等），"
            "体现了地方社会中个人土地权益的动态变化。"
        )
    if top_people:
        top_names = "、".join([p["name"] for p in top_people[:3]])
        parts.append(f"文书网络中的核心人物包括 {top_names} 等，在多份地契中频繁出现。")
    if land_chain_count > 0:
        parts.append(f"同一地块被多次转让的情况共出现 {land_chain_count} 处，反映了土地产权的频繁流动。")
    return "".join(parts)


def call_insights_llm_sync(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
    """调用 LLM 生成跨文档历史洞察（同步）"""
    if not (HAS_DASHSCOPE and settings.DASHSCOPE_API_KEY):
        return _generate_fallback_insights(statistics)
    try:
        prompt = _build_insights_prompt(statistics, parsed_datas)
        response = Generation.call(
            model=Generation.Models.qwen_turbo,
            prompt=prompt,
            result_format="message",
        )
        if response.status_code == 200:
            content = response.output.choices[0].message.content.strip()
            return content if content else _generate_fallback_insights(statistics)
        print(f"LLM洞察生成失败: {response.code} - {response.message}")
    except Exception as e:
        print(f"LLM洞察生成异常: {e}")
    return _generate_fallback_insights(statistics)


async def call_insights_llm(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
    """call_insights_llm_sync 的异步包装"""
    return await run_in_threadpool(call_insights_llm_sync, statistics, parsed_datas)
