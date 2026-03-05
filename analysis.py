import json
import networkx as nx
from typing import Dict, List, Any, Tuple
from sqlalchemy.orm import Session
from database import Document, Entity, Relation

class SocialNetworkAnalyzer:
    def __init__(self, db: Session):
        self.db = db
        self.graph = nx.Graph()

    def build_graph(self):
        """
        Builds a co-occurrence network from database relations.
        Nodes: Entities
        Edges: Co-occurrence in the same document (weighted by frequency)
        """
        # Fetch all documents
        documents = self.db.query(Document).all()
        
        for doc in documents:
            # Get all entities involved in this document
            entities = [r.entity for r in doc.relations]
            
            # Add nodes
            for entity in entities:
                if not self.graph.has_node(entity.id):
                    self.graph.add_node(entity.id, name=entity.name, type=entity.type)
            
            # Add edges (clique for each document)
            # Connect every pair of entities in the document
            import itertools
            for e1, e2 in itertools.combinations(entities, 2):
                if self.graph.has_edge(e1.id, e2.id):
                    self.graph[e1.id][e2.id]['weight'] += 1
                else:
                    self.graph.add_edge(e1.id, e2.id, weight=1)

    def analyze_power_structure(self) -> Dict[str, Any]:
        """
        Calculates centrality metrics and infers social roles (e.g., local gentry, brokers).
        """
        if not self.graph.nodes:
            return {}

        # 1. Centrality Metrics
        try:
            degree_centrality = nx.degree_centrality(self.graph)
            betweenness_centrality = nx.betweenness_centrality(self.graph, weight='weight')
            eigenvector_centrality = nx.eigenvector_centrality(self.graph, max_iter=500, weight='weight')
        except:
            # Fallback if graph is too small or disconnected
            degree_centrality = {n: 0 for n in self.graph.nodes}
            betweenness_centrality = {n: 0 for n in self.graph.nodes}
            eigenvector_centrality = {n: 0 for n in self.graph.nodes}

        # 2. Role Inference (Social Stratification)
        # Logic: High Betweenness + Frequent Middleman Role = Broker/Gentry
        
        node_attributes = {}
        
        for node_id in self.graph.nodes:
            entity = self.db.query(Entity).get(node_id)
            if not entity: continue
            
            # Count roles
            role_counts = {"Seller": 0, "Buyer": 0, "Middleman": 0}
            for r in entity.relations:
                if "Seller" in r.role or "立约" in r.role or "立契" in r.role: role_counts["Seller"] += 1
                elif "Buyer" in r.role: role_counts["Buyer"] += 1
                elif "Middleman" in r.role or "中人" in r.role or "代笔" in r.role or "见证" in r.role: role_counts["Middleman"] += 1
            
            # Inference Rules
            inferred_role = "普通百姓"
            tags = []
            
            # High betweenness often indicates a broker or influential figure
            if betweenness_centrality.get(node_id, 0) > 0.1: 
                tags.append("核心节点")
            
            # Frequent middleman
            if role_counts["Middleman"] >= 3:
                inferred_role = "职业中人/牙行"
                tags.append("中介")
            elif role_counts["Middleman"] > 0 and betweenness_centrality.get(node_id, 0) > 0.05:
                inferred_role = "乡绅/族长" # Influential but maybe not professional broker
                tags.append("权威")
                
            # Frequent buyer (Landlord accumulation)
            if role_counts["Buyer"] >= 3:
                inferred_role = "地主/富户"
                tags.append("土地兼并者")

            node_attributes[node_id] = {
                "name": entity.name,
                "degree": degree_centrality.get(node_id, 0),
                "betweenness": betweenness_centrality.get(node_id, 0),
                "eigenvector": eigenvector_centrality.get(node_id, 0),
                "inferred_role": inferred_role,
                "tags": tags,
                "role_history": role_counts
            }
            
        return node_attributes

    def export_echarts_json(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Formats the graph data for ECharts visualization.
        """
        categories = [
            {"name": "普通百姓"},
            {"name": "职业中人/牙行"},
            {"name": "乡绅/族长"},
            {"name": "地主/富户"},
            {"name": "未知"}
        ]
        
        nodes = []
        for node_id, attr in analysis_results.items():
            # Determine category index
            cat_name = attr["inferred_role"]
            cat_idx = next((i for i, c in enumerate(categories) if c["name"] == cat_name), 0)
            
            # Size based on Degree Centrality (scaled)
            symbol_size = 10 + (attr["degree"] * 50)
            
            nodes.append({
                "id": str(node_id),
                "name": attr["name"],
                "value": attr["betweenness"], # Tooltip value
                "symbolSize": symbol_size,
                "category": cat_idx,
                "label": {"show": True},
                "attributes": attr # Custom data for tooltip
            })
            
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append({
                "source": str(u),
                "target": str(v),
                "value": data['weight']
            })
            
        return {
            "title": {"text": "乡村社会权力网络图谱"},
            "tooltip": {},
            "legend": [{"data": [c["name"] for c in categories]}],
            "series": [{
                "type": "graph",
                "layout": "force",
                "data": nodes,
                "links": edges,
                "categories": categories,
                "roam": True,
                "label": {"position": "right", "formatter": "{b}"},
                "lineStyle": {"color": "source", "curveness": 0.3},
                "force": {"repulsion": 100}
            }]
        }
