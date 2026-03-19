"""
单文档关系图服务
负责从结构化数据构建 ECharts 格式知识图谱，并持久化到 RelationGraph 表。
"""
import json
import re as _re
from typing import Any, Dict

from sqlalchemy.orm import Session

from database import OcrStatus, RelationGraph, StructuredResult, get_beijing_time


def _split_names(raw: str) -> list:
    """
    将多人名字字符串拆分为独立姓名列表。
    支持分隔符：顿号、逗号、空格（连续多个）、换行。
    例："张三、李四" → ["张三", "李四"]
    """
    parts = _re.split(r"[、，,\s]+", raw.strip())
    return [p.strip() for p in parts if p.strip()]


def build_graph_from_structure(data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    """
    基于结构化数据构建单文档关系图。

    图谱结构：
      • 以"地契"为中心契约节点（金色菱形）
      • 卖方/买方/中人支持多人拆分，每人独立节点
      • 卖方 → 地契（出卖）、地契 → 买方（归属）、中人 → 地契（见证）
      • 当卖方和买方均存在时，额外添加卖方 → 买方的直接交易连线
      • 时间/地点/价格/标的 以不同图形的信息节点挂接在地契下方
      • 每个节点携带 properties 字段，供前端点击弹窗展示完整信息

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
        return not val or str(val).strip() in {"未识别", "未知", "None", "未记载", "null", ""}

    def truncate(val: str, max_len: int = 9) -> str:
        s = str(val).strip()
        return s[:max_len] + "…" if len(s) > max_len else s

    # ── 获取背景信息字段（用于丰富人物节点 properties）──────────
    ctx_time     = str(data.get("Time", "")).strip()
    ctx_location = str(data.get("Location", "")).strip()
    ctx_price    = str(data.get("Price", "")).strip()
    ctx_subject  = str(data.get("Subject", "")).strip()

    def person_properties(role: str) -> dict:
        props = {"角色": role}
        if ctx_time     and not is_empty(ctx_time):     props["签约时间"] = ctx_time
        if ctx_location and not is_empty(ctx_location): props["交易地点"] = ctx_location
        if ctx_price    and not is_empty(ctx_price):    props["成交价格"] = ctx_price
        if ctx_subject  and not is_empty(ctx_subject):  props["交易标的"] = ctx_subject
        return props

    # ── 地契中心节点 ──────────────────────────────────────────
    CONTRACT = "地契"
    contract_props: dict = {"类型": "土地买卖契约"}
    if ctx_time     and not is_empty(ctx_time):     contract_props["签约时间"] = ctx_time
    if ctx_location and not is_empty(ctx_location): contract_props["交易地点"] = ctx_location
    if ctx_price    and not is_empty(ctx_price):    contract_props["成交价格"] = ctx_price
    if ctx_subject  and not is_empty(ctx_subject):  contract_props["交易标的"] = ctx_subject

    nodes.append({
        "name": CONTRACT,
        "category": 3,
        "symbolSize": 64,
        "symbol": "diamond",
        "value": "契约凭证",
        "itemStyle": {"color": "#d97706", "borderColor": "#fbbf24", "borderWidth": 3},
        "label": {
            "show": True,
            "position": "inside",
            "fontSize": 15,
            "fontWeight": "bold",
            "color": "#fff",
        },
        "properties": contract_props,
    })

    ROLE_COLORS = {0: "#dc2626", 1: "#2563eb", 2: "#059669"}
    ROLE_NAMES  = {0: "卖方",    1: "买方",    2: "中人"}

    # ── 人物节点添加辅助函数 ──────────────────────────────────
    def add_persons(field_key: str, category_idx: int, rel_label: str, src_is_person: bool):
        """
        支持多人（顿号分隔），每人单独建节点。
        src_is_person=True  → 人物指向地契
        src_is_person=False → 地契指向人物
        """
        raw = data.get(field_key)
        if is_empty(raw):
            return
        names = _split_names(str(raw))
        color = ROLE_COLORS[category_idx]
        role  = ROLE_NAMES[category_idx]

        for i, name in enumerate(names):
            if any(n["name"] == name for n in nodes):
                continue
            nodes.append({
                "name": name,
                "category": category_idx,
                "symbolSize": 46,
                "symbol": "circle",
                "value": role,
                "itemStyle": {"color": color, "borderColor": "#fff", "borderWidth": 2.5},
                "label": {
                    "show": True,
                    "position": "bottom",
                    "fontSize": 13,
                    "fontWeight": "bold",
                    "color": color,
                },
                "properties": person_properties(role),
            })
            # 多人时弧度略有差异，避免连线重叠
            curveness = 0.0 if len(names) == 1 else 0.12 * (i + 1) * (-1 if i % 2 == 0 else 1)
            src, tgt = (name, CONTRACT) if src_is_person else (CONTRACT, name)
            links.append({
                "source": src,
                "target": tgt,
                "value": rel_label,
                "label": {"show": True, "formatter": rel_label, "fontSize": 11, "fontWeight": "bold"},
                "lineStyle": {"width": 2.5, "color": color, "curveness": curveness},
            })

    add_persons("Seller",    0, "出卖", True)
    add_persons("Buyer",     1, "归属", False)
    add_persons("Middleman", 2, "见证", True)

    # ── 卖方 → 买方 直接交易连线（核心交易关系可视化）──────────
    sellers = _split_names(str(data.get("Seller", ""))) if not is_empty(data.get("Seller")) else []
    buyers  = _split_names(str(data.get("Buyer",  ""))) if not is_empty(data.get("Buyer"))  else []
    if sellers and buyers:
        tx_label = "出售" + (f"（{truncate(ctx_price)}）" if ctx_price and not is_empty(ctx_price) else "")
        for seller_name in sellers:
            for buyer_name in buyers:
                links.append({
                    "source": seller_name,
                    "target": buyer_name,
                    "value": tx_label,
                    "label": {"show": True, "formatter": tx_label, "fontSize": 10},
                    "lineStyle": {
                        "width": 1.5,
                        "type": "dashed",
                        "color": "#f59e0b",
                        "curveness": 0.35,
                    },
                })

    # ── 信息节点（时间/地点/价格/标的）────────────────────────
    # 每个字段用不同符号和颜色，便于视觉区分
    INFO_FIELDS = [
        ("Time",     "时间", "pin",       "#0891b2", "#a5f3fc"),
        ("Location", "地点", "pin",       "#0d9488", "#99f6e4"),
        ("Price",    "价格", "rect",      "#7c3aed", "#ddd6fe"),
        ("Subject",  "标的", "roundRect", "#b45309", "#fde68a"),
    ]
    for field_key, field_label, symbol, color, border_color in INFO_FIELDS:
        val = data.get(field_key)
        if is_empty(val):
            continue
        val_str = str(val).strip()
        display_name = f"{field_label}：{truncate(val_str)}"
        nodes.append({
            "name": display_name,
            "category": 4,
            "symbolSize": 32,
            "symbol": symbol,
            "value": val_str,
            "itemStyle": {"color": color, "borderColor": border_color, "borderWidth": 1.5},
            "label": {
                "show": True,
                "position": "bottom",
                "fontSize": 11,
                "color": color,
            },
            "properties": {field_label: val_str},
        })
        links.append({
            "source": CONTRACT,
            "target": display_name,
            "lineStyle": {"type": "dashed", "width": 1.2, "color": color, "opacity": 0.6},
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
        # ② 构建关系图
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
