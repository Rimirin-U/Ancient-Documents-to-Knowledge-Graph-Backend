
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import networkx as nx
from sqlalchemy.orm import Session
from app.core.config import settings
from fastapi.concurrency import run_in_threadpool

from database import (
    StructuredResult, RelationGraph, MultiTask, MultiRelationGraph, 
    OcrResult, OcrStatus, MultiTaskStructuredResult, get_beijing_time
)

# 尝试导入 dashscope，如果不存在则使用模拟
try:
    import dashscope
    from dashscope import Generation
    if settings.DASHSCOPE_API_KEY:
        dashscope.api_key = settings.DASHSCOPE_API_KEY
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False

def _call_llm_sync(text: str) -> Dict[str, Any]:
    """
    调用LLM进行结构化提取 (Sync)
    """
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
                result_format='message'
            )
            
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                # 清理markdown标记
                content = re.sub(r'^```json\s*', '', content)
                content = re.sub(r'\s*```$', '', content)
                return json.loads(content)
            else:
                print(f"LLM调用失败: {response.code} - {response.message}")
                # Fallback to mock
        except Exception as e:
            print(f"LLM调用异常: {e}")
            # Fallback to mock

    # 模拟数据提取逻辑
    return {
        "Time": "未识别",
        "Time_AD": None,
        "Location": "未识别",
        "Seller": "未识别",
        "Buyer": "未识别",
        "Middleman": "未识别",
        "Price": "未识别",
        "Subject": "未识别",
        "Translation": "由于未配置有效的LLM API Key，无法生成翻译和精确提取。请配置DASHSCOPE_API_KEY环境变量。"
    }

async def call_llm_for_structure(text: str) -> Dict[str, Any]:
    return await run_in_threadpool(_call_llm_sync, text)

async def analyze_ocr_result(ocr_result_id: int, db: Session) -> None:
    """
    对OcrResult进行结构化分析
    """
    try:
        # 获取OcrResult
        ocr_result = db.query(OcrResult).filter(OcrResult.id == ocr_result_id).first()
        if not ocr_result:
            print(f"OcrResult {ocr_result_id} not found")
            return
        
        if not ocr_result.raw_text:
            print(f"OcrResult {ocr_result_id} has no text")
            ocr_result.status = OcrStatus.FAILED
            db.commit()
            return

        # 调用分析逻辑
        structured_data = await call_llm_for_structure(ocr_result.raw_text)
        
        # 补充文件名信息
        if ocr_result.image:
             structured_data["filename"] = ocr_result.image.filename

        # 创建StructuredResult
        structured_result = StructuredResult(
            ocr_result_id=ocr_result_id,
            content=json.dumps(structured_data, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=get_beijing_time()
        )
        
        db.add(structured_result)
        db.commit()
        print(f"Structured analysis for {ocr_result_id} completed.")

        # 将 OCR 原文自动索引到 ChromaDB，供 RAG 问答检索
        try:
            from app.services.rag_service import index_document, _get_text_embeddings_sync
            embedding = _get_text_embeddings_sync(ocr_result.raw_text)
            index_document(f"sr_{structured_result.id}", ocr_result.raw_text, embedding)
            print(f"Document sr_{structured_result.id} indexed to ChromaDB.")
        except Exception as idx_err:
            print(f"ChromaDB indexing failed (non-fatal): {idx_err}")

    except Exception as e:
        print(f"Error analyzing OCR result {ocr_result_id}: {str(e)}")
        structured_result = StructuredResult(
            ocr_result_id=ocr_result_id,
            content=json.dumps({"error": str(e)}),
            status=OcrStatus.FAILED,
            created_at=get_beijing_time()
        )
        db.add(structured_result)
        db.commit()


def build_graph_from_structure(data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    """
    基于结构化数据构建单文档关系图。
    以"地契"为中心节点，辐射出人员节点（卖方/买方/中人）和关键信息节点（时间/地点/价格/标的）。

    注意：节点不设 id 字段，连线 source/target 直接使用节点 name，
    确保 ECharts 按 name 匹配端点（设置 id 时 ECharts 优先用 id 匹配会导致连线断开）。
    """
    nodes = []
    links = []
    categories = [
        {"name": "卖方"},
        {"name": "买方"},
        {"name": "中人"},
        {"name": "契约"},
        {"name": "信息"},
    ]

    def is_empty(val) -> bool:
        return not val or str(val).strip() in ["未识别", "未知", "None", ""]

    def truncate(val: str, max_len: int = 10) -> str:
        s = str(val).strip()
        return s[:max_len] + "…" if len(s) > max_len else s

    # ── 中心：地契节点 ──────────────────────────────────────────────
    CONTRACT = "地契"
    nodes.append({
        "name": CONTRACT,
        "category": 3,
        "symbolSize": 62,
        "symbol": "diamond",
        "value": "地契",
        "itemStyle": {"color": "#d97706", "borderColor": "#fbbf24", "borderWidth": 2},
        "label": {
            "show": True,
            "position": "inside",
            "fontSize": 16,
            "fontWeight": "bold",
            "color": "#fff",
        },
    })

    # ── 人员节点 ────────────────────────────────────────────────────
    ROLE_COLORS = {0: "#dc2626", 1: "#2563eb", 2: "#059669"}

    def add_person(field_key: str, category_idx: int, rel_label: str, to_contract: bool):
        val = data.get(field_key)
        if is_empty(val):
            return
        name = str(val).strip()
        if any(n["name"] == name for n in nodes):
            return
        nodes.append({
            "name": name,
            "category": category_idx,
            "symbolSize": 48,
            "symbol": "circle",
            "value": name,
            "itemStyle": {
                "color": ROLE_COLORS[category_idx],
                "borderColor": "#fff",
                "borderWidth": 2,
            },
            "label": {
                "show": True,
                "position": "bottom",
                "fontSize": 13,
                "fontWeight": "bold",
                "color": ROLE_COLORS[category_idx],
            },
        })
        src, tgt = (name, CONTRACT) if to_contract else (CONTRACT, name)
        links.append({
            "source": src,
            "target": tgt,
            "value": rel_label,
            "label": {"show": True, "formatter": rel_label, "fontSize": 11, "fontWeight": "bold"},
            "lineStyle": {"width": 2.5, "color": ROLE_COLORS[category_idx]},
        })

    add_person("Seller",    0, "卖出", True)
    add_person("Buyer",     1, "买入", False)
    add_person("Middleman", 2, "见证", True)

    # ── 信息节点 ────────────────────────────────────────────────────
    info_fields = [
        ("Time",     "时间"),
        ("Time_AD",  "公元"),
        ("Location", "地点"),
        ("Price",    "价格"),
        ("Subject",  "标的"),
    ]

    for field_key, field_label in info_fields:
        val = data.get(field_key)
        if is_empty(val):
            continue
        val_str = str(val).strip()
        display_name = f"公元{val_str}年" if field_key == "Time_AD" else f"{field_label}：{truncate(val_str)}"

        nodes.append({
            "name": display_name,
            "category": 4,
            "symbolSize": 34,
            "symbol": "roundRect",
            "value": val_str,           # 完整原文，悬停 tooltip 中显示
            "itemStyle": {"color": "#7c3aed", "borderColor": "#c4b5fd", "borderWidth": 1},
            "label": {
                "show": True,
                "position": "bottom",
                "fontSize": 11,
                "color": "#5b21b6",
            },
            "tooltip": {"formatter": f"<b>{field_label}</b><br/>{val_str}"},
        })
        # 信息节点与地契之间用虚线连接，不显示边标签
        links.append({
            "source": CONTRACT,
            "target": display_name,
            "lineStyle": {"type": "dashed", "width": 1.5, "color": "#a78bfa", "opacity": 0.7},
        })

    return {
        "type": "graph",
        "layout": "force",
        "categories": categories,
        "data": nodes,
        "links": links,
        "roam": True,
        "label": {"position": "bottom", "formatter": "{b}"},
        "lineStyle": {"curveness": 0.1},
    }

async def analyze_structured_result(structured_result_id: int, db: Session) -> None:
    """
    对StructuredResult进行关系图分析
    """
    try:
        # 获取StructuredResult
        structured_result = db.query(StructuredResult).filter(StructuredResult.id == structured_result_id).first()
        if not structured_result:
            return
        
        try:
            data = json.loads(structured_result.content)
        except json.JSONDecodeError:
            print(f"Invalid JSON content in StructuredResult {structured_result_id}")
            return
            
        # 构建关系图
        graph_data = build_graph_from_structure(data, str(structured_result_id))
        
        # 封装成ECharts格式
        echarts_option = {
            "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c}"},
            "legend": [{"data": ["卖方", "买方", "中人", "契约", "信息"], "bottom": 4}],
            "series": [graph_data]
        }

        # 创建RelationGraph
        relation_graph = RelationGraph(
            structured_result_id=structured_result_id,
            content=json.dumps(echarts_option, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=get_beijing_time()
        )
        
        db.add(relation_graph)
        db.commit()
        print(f"Relation graph analysis for {structured_result_id} completed.")
        
    except Exception as e:
        print(f"Error analyzing structured result {structured_result_id}: {str(e)}")
        relation_graph = RelationGraph(
            structured_result_id=structured_result_id,
            content=json.dumps({"error": str(e)}),
            status=OcrStatus.FAILED,
            created_at=get_beijing_time()
        )
        db.add(relation_graph)
        db.commit()


from app.services.analysis_components.entity_resolver import EntityResolver

# ─────────────────────────────────────────────────────────────
#  LLM 洞察生成
# ─────────────────────────────────────────────────────────────

def _build_insights_prompt(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
    """根据统计数据构造 LLM 分析提示词"""
    doc_count = statistics.get("doc_count", 0)
    time_range = statistics.get("time_range", {})
    unique_people = statistics.get("unique_people", 0)
    cross_role = statistics.get("cross_role_people", [])
    top_people = statistics.get("top_people", [])
    top_locations = statistics.get("top_locations", [])
    land_chain_count = statistics.get("land_chain_count", 0)

    if time_range.get("start") and time_range.get("end"):
        time_str = f"公元 {time_range['start']} 年 — {time_range['end']} 年（跨度 {time_range.get('span', 0)} 年）"
    else:
        time_str = "时间信息不完整"

    summaries = []
    for d in parsed_datas[:8]:
        seller = d.get("Seller", "")
        buyer = d.get("Buyer", "")
        loc = d.get("Location", "")
        price = d.get("Price", "")
        t = d.get("Time", "")
        if seller and buyer and all(v not in ["未识别", "未知", ""] for v in [seller, buyer]):
            parts = [f"{t}：" if t and t not in ["未识别", ""] else ""]
            parts.append(f"{seller} → {buyer}")
            if loc and loc not in ["未识别", ""]:
                parts.append(f"，地点：{loc}")
            if price and price not in ["未识别", ""]:
                parts.append(f"，价格：{price}")
            summaries.append("  - " + "".join(parts))

    cross_str = "、".join(cross_role[:5]) if cross_role else "无"
    top_people_str = "、".join(
        [f"{p['name']}（涉及 {p['doc_count']} 份文书）" for p in top_people[:3]]
    ) if top_people else "数据不足"
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
请选择有数据支撑的角度进行分析，例如：
1. 这批文书反映的社会关系网络结构特征
2. 核心人物在地方经济中扮演的角色
3. 地产多次易手的历史规律或原因推测
4. 时代背景与人物活动的关联（如有明确时间）

要求：基于数据客观分析，语言专业凝练，不臆测无据内容，不超过250字。"""


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
            f"时间跨度从公元 {time_range['start']} 年至 {time_range['end']} 年（历时约 {time_range.get('span', 0)} 年），"
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


def _call_llm_insights_sync(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
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
        else:
            print(f"LLM insights 调用失败: {response.code} - {response.message}")
            return _generate_fallback_insights(statistics)
    except Exception as e:
        print(f"LLM insights 调用异常: {e}")
        return _generate_fallback_insights(statistics)


async def call_llm_for_insights(statistics: Dict[str, Any], parsed_datas: List[Dict]) -> str:
    return await run_in_threadpool(_call_llm_insights_sync, statistics, parsed_datas)


# ─────────────────────────────────────────────────────────────
#  跨文档分析主函数（增强版）
# ─────────────────────────────────────────────────────────────

_EMPTY_VALS = {"未识别", "未知", "None", "none", ""}


def _is_empty(val: Any) -> bool:
    return not val or str(val).strip() in _EMPTY_VALS


async def analyze_multi_task(multi_task_id: int, db: Session) -> None:
    """
    对 MultiTask 进行跨文档分析（增强版）

    新增能力：
    1. 中文图例（卖方/买方/中人/地块/跨角色）
    2. 地产流转节点：同一地点 2+ 次交易时生成"地块"节点，连接各交易方
    3. 跨角色人物：在不同文书中身兼多职的人物以紫色菱形显示
    4. 统计数据：时间跨度、核心人物、主要地点、地产链
    5. LLM 历史洞察：调用 LLM 生成自然语言分析摘要
    """
    try:
        multi_task = db.query(MultiTask).filter(MultiTask.id == multi_task_id).first()
        if not multi_task:
            return

        associations = db.query(MultiTaskStructuredResult).filter(
            MultiTaskStructuredResult.multi_task_id == multi_task_id
        ).all()
        sr_ids = [a.structured_result_id for a in associations]
        structured_results = db.query(StructuredResult).filter(
            StructuredResult.id.in_(sr_ids)
        ).all()

        if not structured_results:
            print(f"No structured results for MultiTask {multi_task_id}")
            return

        # ── 解析所有文档数据 ──────────────────────────────────────
        parsed_datas: List[Dict] = []
        for sr in structured_results:
            try:
                parsed_datas.append(json.loads(sr.content))
            except json.JSONDecodeError:
                parsed_datas.append({})

        # ── CPU密集型图构建（threadpool中运行） ──────────────────
        def _build_merged_graph():
            from collections import Counter, defaultdict

            G = nx.Graph()

            # 1. 收集原始节点
            raw_nodes = []
            for sr, data in zip(structured_results, parsed_datas):
                doc_id = str(sr.id)
                time_ad = data.get("Time_AD")
                location = data.get("Location", "").strip()
                if location in _EMPTY_VALS:
                    location = ""
                for role in ["Seller", "Buyer", "Middleman"]:
                    name = str(data.get(role, "")).strip()
                    if name and name not in _EMPTY_VALS:
                        raw_nodes.append({
                            "original_name": name,
                            "role": role,
                            "doc_id": doc_id,
                            "time_ad": time_ad,
                            "location": location,
                            "data": data,
                        })

            # 2. 实体消歧
            merged_entities = EntityResolver.resolve_entities(raw_nodes)

            # 名称 → 实体的查找索引
            name_to_entity: Dict[str, Dict] = {}
            for entity in merged_entities:
                for inst in entity["instances"]:
                    name_to_entity[inst["original_name"]] = entity

            # 3. 统计信息计算
            location_counter: Counter = Counter()
            int_years: List[int] = []
            for data in parsed_datas:
                loc = str(data.get("Location", "")).strip()
                if loc and loc not in _EMPTY_VALS:
                    location_counter[loc] += 1
                try:
                    y = int(data.get("Time_AD", ""))
                    int_years.append(y)
                except (ValueError, TypeError):
                    pass

            time_range: Dict[str, Any] = {}
            if int_years:
                time_range = {
                    "start": min(int_years),
                    "end": max(int_years),
                    "span": max(int_years) - min(int_years),
                    "docs_with_time": len(int_years),
                }

            top_people = sorted(
                merged_entities,
                key=lambda e: len(set(i["doc_id"] for i in e["instances"])),
                reverse=True,
            )[:5]

            # 地产流转：出现 2+ 次的地点
            land_locations = {loc for loc, cnt in location_counter.items() if cnt >= 2}
            land_chains = []
            for loc in land_locations:
                docs_here = [
                    {"time_ad": d.get("Time_AD"), "seller": d.get("Seller", ""), "buyer": d.get("Buyer", "")}
                    for d in parsed_datas
                    if str(d.get("Location", "")).strip() == loc
                ]
                try:
                    years = sorted(
                        int(dd["time_ad"]) for dd in docs_here
                        if dd.get("time_ad") and str(dd["time_ad"]) not in _EMPTY_VALS
                    )
                except Exception:
                    years = []
                land_chains.append({
                    "location": loc,
                    "transaction_count": location_counter[loc],
                    "years": years,
                })

            statistics = {
                "doc_count": len(structured_results),
                "time_range": time_range,
                "unique_people": len(merged_entities),
                "cross_role_people": [
                    e["standard_name"] for e in merged_entities if e.get("cross_role")
                ],
                "top_people": [
                    {
                        "name": e["standard_name"],
                        "doc_count": len(set(i["doc_id"] for i in e["instances"])),
                        "roles": list(set(i["role"] for i in e["instances"])),
                    }
                    for e in top_people
                ],
                "top_locations": [
                    {"name": loc, "count": cnt}
                    for loc, cnt in location_counter.most_common(5)
                ],
                "land_chain_count": len(land_chains),
                "land_chains": land_chains[:5],
            }

            # 4. 构建 NetworkX 图
            # 类别：0=卖方 1=买方 2=中人 3=地块 4=跨角色
            CATEGORY_MAP = {"Seller": 0, "Buyer": 1, "Middleman": 2}
            ROLE_ZH = {"Seller": "卖方", "Buyer": "买方", "Middleman": "中人"}

            NODE_COLORS = {
                0: "#dc2626",   # 卖方 红
                1: "#2563eb",   # 买方 蓝
                2: "#059669",   # 中人 绿
                3: "#d97706",   # 地块 琥珀
                4: "#7c3aed",   # 跨角色 紫
            }
            NODE_BORDER = {
                0: "#fca5a5", 1: "#93c5fd", 2: "#6ee7b7",
                3: "#fcd34d", 4: "#c4b5fd",
            }

            cross_role_names = {e["standard_name"] for e in merged_entities if e.get("cross_role")}

            # 添加人物节点
            for entity in merged_entities:
                name = entity["standard_name"]
                doc_count_e = len(set(i["doc_id"] for i in entity["instances"]))
                is_cross = name in cross_role_names
                cat_idx = 4 if is_cross else CATEGORY_MAP.get(entity["role"], 0)
                roles_zh = "/".join(ROLE_ZH.get(r, r) for r in sorted(set(i["role"] for i in entity["instances"])))

                G.add_node(name,
                           category=cat_idx,
                           doc_count=doc_count_e,
                           roles_zh=roles_zh,
                           cross_role=is_cross)

            # 添加地块节点
            for loc in land_locations:
                land_id = f"[地块]{loc}"
                G.add_node(land_id, category=3, doc_count=location_counter[loc],
                           roles_zh="地块", cross_role=False)

            # 5. 添加边

            # 按文档逐条处理
            doc_entity_map: Dict[str, Dict[str, str]] = defaultdict(dict)
            for entity in merged_entities:
                for inst in entity["instances"]:
                    doc_entity_map[inst["doc_id"]][inst["role"]] = entity["standard_name"]

            for sr, data in zip(structured_results, parsed_datas):
                doc_id = str(sr.id)
                de = doc_entity_map.get(doc_id, {})
                seller = de.get("Seller")
                buyer = de.get("Buyer")
                middleman = de.get("Middleman")
                time_label = str(data.get("Time_AD", "")).strip()
                if time_label in _EMPTY_VALS:
                    time_label = data.get("Time", "").strip()
                if time_label in _EMPTY_VALS:
                    time_label = ""

                # 买卖关系
                if seller and buyer and G.has_node(seller) and G.has_node(buyer):
                    edge_label = f"出售{'·' + time_label if time_label else ''}"
                    if G.has_edge(seller, buyer):
                        G[seller][buyer]["doc_ids"] = G[seller][buyer].get("doc_ids", []) + [doc_id]
                        G[seller][buyer]["count"] = G[seller][buyer].get("count", 1) + 1
                    else:
                        G.add_edge(seller, buyer, relation="Trade",
                                   label=edge_label, doc_ids=[doc_id], count=1)

                # 见证关系
                for party in [seller, buyer]:
                    if middleman and party and G.has_node(middleman) and G.has_node(party):
                        if G.has_edge(middleman, party):
                            G[middleman][party]["count"] = G[middleman][party].get("count", 1) + 1
                        else:
                            G.add_edge(middleman, party, relation="Witness",
                                       label="见证", doc_ids=[doc_id], count=1)

                # 地产流转：连接各方与地块节点
                loc = str(data.get("Location", "")).strip()
                if loc and loc not in _EMPTY_VALS and loc in land_locations:
                    land_id = f"[地块]{loc}"
                    for party in [seller, buyer]:
                        if party and G.has_node(party) and G.has_node(land_id):
                            edge_label = f"{'出让' if party == seller else '受让'}{'·' + time_label if time_label else ''}"
                            if not G.has_edge(land_id, party):
                                G.add_edge(land_id, party, relation="LandChange",
                                           label=edge_label, doc_ids=[doc_id], count=1)

            # 6. 转换为 ECharts force-layout 格式
            try:
                degree_centrality = nx.degree_centrality(G)
            except Exception:
                degree_centrality = {}

            categories = [
                {"name": "卖方"},
                {"name": "买方"},
                {"name": "中人"},
                {"name": "地块"},
                {"name": "跨角色"},
            ]

            echarts_nodes = []
            for node in G.nodes():
                attrs = G.nodes[node]
                cat_idx = attrs.get("category", 0)
                doc_cnt = attrs.get("doc_count", 1)
                centrality = degree_centrality.get(node, 0)
                is_land = cat_idx == 3

                base_size = 38 if is_land else 28
                size = min(80, base_size + centrality * 55 + doc_cnt * 6)

                color = NODE_COLORS.get(cat_idx, "#6b7280")
                border = NODE_BORDER.get(cat_idx, "#d1d5db")
                symbol = "roundRect" if is_land else ("diamond" if cat_idx == 4 else "circle")

                display_name = node.replace("[地块]", "") if is_land else node
                roles_zh = attrs.get("roles_zh", "")
                tooltip_text = (
                    f"地块：{display_name}<br/>交易次数：{doc_cnt}"
                    if is_land
                    else f"{display_name}<br/>角色：{roles_zh}<br/>涉及文书：{doc_cnt} 份"
                )

                echarts_nodes.append({
                    "name": node,
                    "category": cat_idx,
                    "symbolSize": size,
                    "symbol": symbol,
                    "value": tooltip_text,
                    "label": {
                        "show": True,
                        "formatter": display_name,
                        "position": "bottom",
                        "fontSize": 12,
                        "fontWeight": "bold" if doc_cnt >= 2 else "normal",
                        "color": color,
                    },
                    "itemStyle": {
                        "color": color,
                        "borderColor": border,
                        "borderWidth": 2,
                        "opacity": 1.0,
                    },
                })

            RELATION_STYLES = {
                "Trade": {
                    "color": "#1e40af",
                    "width": 3,
                    "type": "solid",
                    "opacity": 0.85,
                },
                "Witness": {
                    "color": "#059669",
                    "width": 2,
                    "type": "dashed",
                    "opacity": 0.7,
                },
                "LandChange": {
                    "color": "#b45309",
                    "width": 2.5,
                    "type": "solid",
                    "opacity": 0.8,
                },
            }

            echarts_links = []
            for u, v, edata in G.edges(data=True):
                rel = edata.get("relation", "Trade")
                style = RELATION_STYLES.get(rel, RELATION_STYLES["Trade"])
                count = edata.get("count", 1)
                lbl = edata.get("label", rel)
                if count > 1:
                    lbl = f"{lbl}(×{count})"

                echarts_links.append({
                    "source": u,
                    "target": v,
                    "value": lbl,
                    "label": {
                        "show": True,
                        "formatter": lbl,
                        "fontSize": 10,
                        "fontWeight": "bold",
                        "backgroundColor": "rgba(255,255,255,0.7)",
                        "borderRadius": 3,
                        "padding": [2, 4],
                    },
                    "lineStyle": {
                        "color": style["color"],
                        "width": style["width"] + (count - 1) * 0.5,
                        "type": style["type"],
                        "opacity": style["opacity"],
                    },
                })

            echarts_option = {
                "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c}"},
                "legend": [
                    {
                        "data": ["卖方", "买方", "中人", "地块", "跨角色"],
                        "bottom": 4,
                        "textStyle": {"fontSize": 11},
                        "itemWidth": 12,
                        "itemHeight": 12,
                        "icon": "circle",
                    }
                ],
                "series": [
                    {
                        "type": "graph",
                        "layout": "force",
                        "categories": categories,
                        "data": echarts_nodes,
                        "links": echarts_links,
                        "roam": True,
                        "label": {"position": "bottom", "formatter": "{b}"},
                        "force": {
                            "repulsion": 800,
                            "edgeLength": [80, 220],
                            "gravity": 0.1,
                            "layoutAnimation": True,
                            "friction": 0.6,
                        },
                        "emphasis": {
                            "focus": "adjacency",
                            "lineStyle": {"width": 5},
                            "label": {"show": True, "fontWeight": "bold"},
                            "itemStyle": {"shadowBlur": 12, "shadowColor": "rgba(0,0,0,0.35)"},
                        },
                        "blur": {
                            "itemStyle": {"opacity": 0.2},
                            "lineStyle": {"opacity": 0.1},
                            "label": {"opacity": 0.25},
                        },
                    }
                ],
                # 统计数据与洞察（前端额外展示）
                "statistics": statistics,
            }

            return echarts_option, statistics, parsed_datas

        # ── 在 threadpool 中运行图构建 ──────────────────────────
        echarts_option, statistics, parsed_datas_out = await run_in_threadpool(_build_merged_graph)

        # ── 调用 LLM 生成历史洞察 ───────────────────────────────
        insights = await call_llm_for_insights(statistics, parsed_datas_out)
        echarts_option["insights"] = insights

        # ── 持久化 ──────────────────────────────────────────────
        multi_relation_graph = MultiRelationGraph(
            multi_task_id=multi_task_id,
            content=json.dumps(echarts_option, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=get_beijing_time(),
        )
        db.add(multi_relation_graph)
        db.commit()
        print(f"Multi-task analysis for {multi_task_id} completed (enhanced).")

    except Exception as e:
        print(f"Error analyzing multi task {multi_task_id}: {str(e)}")
        multi_relation_graph = MultiRelationGraph(
            multi_task_id=multi_task_id,
            content=json.dumps({"error": str(e)}),
            status=OcrStatus.FAILED,
            created_at=get_beijing_time(),
        )
        db.add(multi_relation_graph)
        db.commit()
