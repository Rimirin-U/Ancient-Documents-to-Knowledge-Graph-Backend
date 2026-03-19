"""
单文档关系图服务
负责从结构化数据构建 ECharts 格式知识图谱，并持久化到 RelationGraph 表。
"""
import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from database import OcrStatus, RelationGraph, StructuredResult, get_beijing_time


def build_graph_from_structure(data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    """
    基于结构化数据构建单文档关系图。
    以"地契"为中心节点，辐射出人员节点（卖方/买方/中人）和关键信息节点（时间/地点/价格/标的）。

    注意：节点不设 id 字段，连线 source/target 直接使用节点 name，
    确保 ECharts 按 name 匹配端点。
    """
    nodes: list = []
    links: list = []
    categories = [
        {"name": "卖方"},
        {"name": "买方"},
        {"name": "中人"},
        {"name": "契约"},
        {"name": "信息"},
    ]

    def is_empty(val) -> bool:
        return not val or str(val).strip() in {"未识别", "未知", "None", ""}

    def truncate(val: str, max_len: int = 10) -> str:
        s = str(val).strip()
        return s[:max_len] + "…" if len(s) > max_len else s

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
            "value": val_str,
            "itemStyle": {"color": "#7c3aed", "borderColor": "#c4b5fd", "borderWidth": 1},
            "label": {
                "show": True,
                "position": "bottom",
                "fontSize": 11,
                "color": "#5b21b6",
            },
            "tooltip": {"formatter": f"<b>{field_label}</b><br/>{val_str}"},
        })
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
    对 StructuredResult 构建单文档关系图并持久化。
    先写入 PROCESSING 状态，构建完成后更新，确保前端触发后立即能查询到记录 ID。
    """
    structured_result = (
        db.query(StructuredResult)
        .filter(StructuredResult.id == structured_result_id)
        .first()
    )
    if not structured_result:
        return

    try:
        data = json.loads(structured_result.content)
    except json.JSONDecodeError:
        print(f"Invalid JSON in StructuredResult {structured_result_id}")
        return

    # ① 立即写入 PROCESSING 状态
    relation_graph = RelationGraph(
        structured_result_id=structured_result_id,
        content=json.dumps({}),
        status=OcrStatus.PROCESSING,
        created_at=get_beijing_time(),
    )
    db.add(relation_graph)
    db.commit()
    db.refresh(relation_graph)

    try:
        # ② 构建关系图（CPU 密集，但数据量小，同步即可）
        graph_data = build_graph_from_structure(data, str(structured_result_id))
        echarts_option = {
            "tooltip": {"trigger": "item", "formatter": "{b}<br/>{c}"},
            "legend": [{"data": ["卖方", "买方", "中人", "契约", "信息"], "bottom": 4}],
            "series": [graph_data],
        }

        # ③ 更新为 DONE 状态
        relation_graph.content = json.dumps(echarts_option, ensure_ascii=False)
        relation_graph.status = OcrStatus.DONE
        db.commit()
        print(f"Relation graph for StructuredResult {structured_result_id} completed.")

    except Exception as e:
        print(f"Error building relation graph {structured_result_id}: {e}")
        relation_graph.content = json.dumps({"error": str(e)})
        relation_graph.status = OcrStatus.FAILED
        db.commit()
