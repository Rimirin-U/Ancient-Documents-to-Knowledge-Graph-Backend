
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import networkx as nx
from sqlalchemy.orm import Session

from database import (
    StructuredResult, RelationGraph, MultiTask, MultiRelationGraph, 
    OcrResult, OcrStatus, MultiTaskStructuredResult
)

# 尝试导入 dashscope，如果不存在则使用模拟
try:
    import dashscope
    from dashscope import Generation
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
    if DASHSCOPE_API_KEY:
        dashscope.api_key = DASHSCOPE_API_KEY
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False

def call_llm_for_structure(text: str) -> Dict[str, Any]:
    """
    调用LLM进行结构化提取
    如果配置了DashScope且有API Key，则调用通义千问
    否则返回模拟数据
    """
    if HAS_DASHSCOPE and os.getenv("DASHSCOPE_API_KEY"):
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

    # 模拟数据提取逻辑 (简单的正则或规则，仅作演示)
    # 在实际没有LLM的情况下，这里应该尽可能用规则提取
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

def analyze_ocr_result(ocr_result_id: int, db: Session) -> None:
    """
    对OcrResult进行结构化分析
    
    Args:
        ocr_result_id: OCR结果的ID
        db: 数据库会话
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

        # 更新状态
        # ocr_result.status = OcrStatus.PROCESSING # 已经是PROCESSING或DONE，这里不改OCR状态，而是创建新的记录
        
        # 调用分析逻辑
        structured_data = call_llm_for_structure(ocr_result.raw_text)
        
        # 补充文件名信息
        if ocr_result.image:
             structured_data["filename"] = ocr_result.image.filename

        # 创建StructuredResult
        structured_result = StructuredResult(
            ocr_result_id=ocr_result_id,
            content=json.dumps(structured_data, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(structured_result)
        db.commit()
        print(f"Structured analysis for {ocr_result_id} completed.")
        
    except Exception as e:
        print(f"Error analyzing OCR result {ocr_result_id}: {str(e)}")
        # 可以选择创建一个状态为FAILED的StructuredResult
        structured_result = StructuredResult(
            ocr_result_id=ocr_result_id,
            content=json.dumps({"error": str(e)}),
            status=OcrStatus.FAILED,
            created_at=datetime.now(timezone.utc)
        )
        db.add(structured_result)
        db.commit()


def build_graph_from_structure(data: Dict[str, Any], doc_id: str) -> Dict[str, Any]:
    """
    基于结构化数据构建单文档关系图
    """
    nodes = []
    links = []
    categories = [{"name": "Seller"}, {"name": "Buyer"}, {"name": "Middleman"}, {"name": "Other"}]
    
    # 辅助函数：添加节点
    def add_node(name, category, role):
        if not name or name in ["未识别", "未知", ""]:
            return
        
        # 检查节点是否已存在
        for node in nodes:
            if node["name"] == name:
                return
        
        nodes.append({
            "id": f"{doc_id}_{name}", # 使用文档ID前缀防止冲突，或者在单图分析中直接用名字
            "name": name,
            "category": category,
            "symbolSize": 20,
            "value": 1,
            "attributes": {
                "role": role,
                "doc_id": doc_id
            }
        })

    seller = data.get("Seller")
    buyer = data.get("Buyer")
    middleman = data.get("Middleman")
    
    if seller:
        add_node(seller, 0, "Seller")
    if buyer:
        add_node(buyer, 1, "Buyer")
    if middleman:
        add_node(middleman, 2, "Middleman")
        
    # 添加边
    if seller and buyer:
        links.append({
            "source": f"{doc_id}_{seller}",
            "target": f"{doc_id}_{buyer}",
            "value": "Trade",
            "label": {"show": True, "formatter": "交易"}
        })
    
    if middleman and seller:
        links.append({
            "source": f"{doc_id}_{middleman}",
            "target": f"{doc_id}_{seller}",
            "value": "Witness",
            "label": {"show": True, "formatter": "见证"}
        })
        
    if middleman and buyer:
        links.append({
            "source": f"{doc_id}_{middleman}",
            "target": f"{doc_id}_{buyer}",
            "value": "Witness",
            "label": {"show": True, "formatter": "见证"}
        })

    return {
        "type": "graph",
        "layout": "force",
        "categories": categories,
        "data": nodes,
        "links": links,
        "roam": True,
        "label": {"position": "right", "formatter": "{b}"},
        "lineStyle": {"color": "source", "curveness": 0.3}
    }

def analyze_structured_result(structured_result_id: int, db: Session) -> None:
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
            "title": {"text": "地契关系图"},
            "tooltip": {},
            "legend": [{"data": ["Seller", "Buyer", "Middleman", "Other"]}],
            "series": [graph_data]
        }

        # 创建RelationGraph
        relation_graph = RelationGraph(
            structured_result_id=structured_result_id,
            content=json.dumps(echarts_option, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=datetime.now(timezone.utc)
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
            created_at=datetime.now(timezone.utc)
        )
        db.add(relation_graph)
        db.commit()


def analyze_multi_task(multi_task_id: int, db: Session) -> None:
    """
    对MultiTask进行跨文档分析
    """
    try:
        # 获取MultiTask及其关联的StructuredResult
        multi_task = db.query(MultiTask).filter(MultiTask.id == multi_task_id).first()
        if not multi_task:
            return
            
        associations = db.query(MultiTaskStructuredResult).filter(MultiTaskStructuredResult.multi_task_id == multi_task_id).all()
        structured_results = []
        for assoc in associations:
            sr = db.query(StructuredResult).filter(StructuredResult.id == assoc.structured_result_id).first()
            if sr:
                structured_results.append(sr)
        
        if not structured_results:
            print(f"No structured results found for MultiTask {multi_task_id}")
            return

        # 使用NetworkX构建合并图
        G = nx.Graph()
        
        node_attributes = {} # 存储节点属性
        
        for sr in structured_results:
            try:
                data = json.loads(sr.content)
                doc_id = str(sr.id)
                
                seller = data.get("Seller")
                buyer = data.get("Buyer")
                middleman = data.get("Middleman")
                
                # 简单的实体消歧：假设同名即同人
                # 实际项目中这里需要更复杂的实体对齐算法
                
                if seller and seller not in ["未识别", "未知"]:
                    G.add_node(seller, category="Seller")
                    node_attributes[seller] = {"role": "Seller", "docs": node_attributes.get(seller, {}).get("docs", []) + [doc_id]}
                    
                if buyer and buyer not in ["未识别", "未知"]:
                    G.add_node(buyer, category="Buyer")
                    node_attributes[buyer] = {"role": "Buyer", "docs": node_attributes.get(buyer, {}).get("docs", []) + [doc_id]}
                    
                if middleman and middleman not in ["未识别", "未知"]:
                    G.add_node(middleman, category="Middleman")
                    node_attributes[middleman] = {"role": "Middleman", "docs": node_attributes.get(middleman, {}).get("docs", []) + [doc_id]}
                
                # 添加边
                if seller and buyer:
                    G.add_edge(seller, buyer, relation="Trade", doc_id=doc_id)
                if middleman and seller:
                    G.add_edge(middleman, seller, relation="Witness", doc_id=doc_id)
                if middleman and buyer:
                    G.add_edge(middleman, buyer, relation="Witness", doc_id=doc_id)
                    
            except json.JSONDecodeError:
                continue

        # 转换为ECharts格式
        nodes = []
        categories = [{"name": "Seller"}, {"name": "Buyer"}, {"name": "Middleman"}]
        category_map = {"Seller": 0, "Buyer": 1, "Middleman": 2}
        
        # 计算中心性指标
        try:
            degree_centrality = nx.degree_centrality(G)
        except:
            degree_centrality = {}
            
        for node in G.nodes():
            cat_name = G.nodes[node].get("category", "Seller")
            cat_idx = category_map.get(cat_name, 0)
            
            # 根据度中心性调整节点大小
            size = 20 + (degree_centrality.get(node, 0) * 50)
            
            nodes.append({
                "id": node,
                "name": node,
                "category": cat_idx,
                "symbolSize": size,
                "value": degree_centrality.get(node, 0),
                "attributes": node_attributes.get(node, {})
            })
            
        links = []
        for u, v, data in G.edges(data=True):
            links.append({
                "source": u,
                "target": v,
                "value": data.get("relation", "link"),
                "label": {"show": True, "formatter": data.get("relation", "")}
            })
            
        echarts_option = {
            "title": {"text": "跨文档社会关系网络"},
            "tooltip": {},
            "legend": [{"data": ["Seller", "Buyer", "Middleman"]}],
            "series": [{
                "type": "graph",
                "layout": "force",
                "categories": categories,
                "data": nodes,
                "links": links,
                "roam": True,
                "label": {"position": "right", "formatter": "{b}"},
                "force": {
                    "repulsion": 100
                }
            }]
        }
        
        # 创建MultiRelationGraph
        multi_relation_graph = MultiRelationGraph(
            multi_task_id=multi_task_id,
            content=json.dumps(echarts_option, ensure_ascii=False),
            status=OcrStatus.DONE,
            created_at=datetime.now(timezone.utc)
        )
        
        db.add(multi_relation_graph)
        db.commit()
        print(f"Multi-task analysis for {multi_task_id} completed.")
        
    except Exception as e:
        print(f"Error analyzing multi task {multi_task_id}: {str(e)}")
        multi_relation_graph = MultiRelationGraph(
            multi_task_id=multi_task_id,
            content=json.dumps({"error": str(e)}),
            status=OcrStatus.FAILED,
            created_at=datetime.now(timezone.utc)
        )
        db.add(multi_relation_graph)
        db.commit()
