
from typing import List, Dict, Any
from collections import Counter


class EntityResolver:
    """
    古籍地契实体消歧解析器（增强版）

    改进要点：
    - 中文人名字符级 Jaccard 模糊相似度，处理字号/别名场景
    - 多实例平均评分，避免代表性偏差
    - 标准名智能优选（最长 + 高频）
    - 跨角色检测（同一人在不同文书中先买后卖等）
    - 合并阈值调低至 0.45，减少漏判
    """

    @staticmethod
    def _char_jaccard(s1: str, s2: str) -> float:
        """字符集合 Jaccard 相似度，适合短中文姓名"""
        if not s1 or not s2:
            return 0.0
        set1, set2 = set(s1), set(s2)
        inter = len(set1 & set2)
        union = len(set1 | set2)
        return inter / union if union > 0 else 0.0

    @staticmethod
    def _name_similarity(name1: str, name2: str) -> float:
        """
        综合人名相似度（0~1）：
          完全匹配 → 1.0
          包含关系（字号/别名） → 0.75
          Jaccard ≥ 0.4 → Jaccard 值
          其余 → 0.0（直接排除）
        """
        if name1 == name2:
            return 1.0
        if name1 in name2 or name2 in name1:
            return 0.75
        jaccard = EntityResolver._char_jaccard(name1, name2)
        return jaccard if jaccard >= 0.4 else 0.0

    @staticmethod
    def calculate_similarity(node1_attrs: Dict, node2_attrs: Dict) -> float:
        """
        多维度综合相似度（0~1）：
          姓名 50% + 时间 25% + 地点 25%

        注：角色不同不扣分，支持跨角色同一人场景。
        """
        name1 = str(node1_attrs.get("name", "")).strip()
        name2 = str(node2_attrs.get("name", "")).strip()

        name_sim = EntityResolver._name_similarity(name1, name2)
        if name_sim == 0.0:
            return 0.0

        score = name_sim * 0.5

        # 时间维度：年份差越小，加分越多
        t1 = node1_attrs.get("time_ad")
        t2 = node2_attrs.get("time_ad")
        if t1 and t2:
            try:
                diff = abs(int(t1) - int(t2))
                if diff <= 3:
                    score += 0.25
                elif diff <= 10:
                    score += 0.18
                elif diff <= 30:
                    score += 0.10
                elif diff <= 60:
                    score += 0.05
            except (ValueError, TypeError):
                pass

        # 地点维度
        loc1 = str(node1_attrs.get("location", "")).strip()
        loc2 = str(node2_attrs.get("location", "")).strip()
        if loc1 and loc2:
            if loc1 == loc2:
                score += 0.25
            elif loc1 in loc2 or loc2 in loc1:
                score += 0.18
            else:
                prefix_len = min(3, len(loc1), len(loc2))
                if prefix_len >= 2 and loc1[:prefix_len] == loc2[:prefix_len]:
                    score += 0.10

        return score

    @staticmethod
    def _select_standard_name(instances: List[Dict]) -> str:
        """
        从多个实例中优选标准名：
        优先最长（通常最完整），同长度中选最高频。
        """
        names = [inst["original_name"] for inst in instances]
        max_len = max(len(n) for n in names)
        longest = [n for n in names if len(n) == max_len]
        freq = Counter(names)
        return max(longest, key=lambda n: freq[n])

    @staticmethod
    def resolve_entities(raw_nodes: List[Dict]) -> List[Dict[str, Any]]:
        """
        执行实体消歧，合并阈值 0.45（使用全部实例的平均得分）。

        返回合并后实体列表，每条包含：
          id, standard_name, role (主要角色), roles (所有角色),
          cross_role (是否跨角色), instances (原始记录列表)
        """
        merged: List[Dict] = []
        THRESHOLD = 0.45

        for node in raw_nodes:
            node_attrs = {
                "name": node["original_name"],
                "role": node["role"],
                "time_ad": node.get("time_ad"),
                "location": node.get("location"),
            }

            best_score, best_idx = 0.0, -1

            for idx, entity in enumerate(merged):
                scores = []
                for inst in entity["instances"]:
                    inst_attrs = {
                        "name": inst["original_name"],
                        "role": inst["role"],
                        "time_ad": inst.get("time_ad"),
                        "location": inst.get("location"),
                    }
                    scores.append(EntityResolver.calculate_similarity(node_attrs, inst_attrs))
                avg = sum(scores) / len(scores) if scores else 0.0
                if avg >= THRESHOLD and avg > best_score:
                    best_score = avg
                    best_idx = idx

            if best_idx >= 0:
                merged[best_idx]["instances"].append(node)
                merged[best_idx]["standard_name"] = EntityResolver._select_standard_name(
                    merged[best_idx]["instances"]
                )
                all_roles = set(inst["role"] for inst in merged[best_idx]["instances"])
                merged[best_idx]["roles"] = list(all_roles)
                merged[best_idx]["cross_role"] = len(all_roles) > 1
            else:
                merged.append({
                    "id": f"entity_{len(merged)}",
                    "standard_name": node["original_name"],
                    "role": node["role"],
                    "roles": [node["role"]],
                    "cross_role": False,
                    "instances": [node],
                })

        return merged
