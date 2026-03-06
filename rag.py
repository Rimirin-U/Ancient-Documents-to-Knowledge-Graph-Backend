
import json
import os
import dashscope
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from database import StructuredResult

# RAG 配置
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
if DASHSCOPE_API_KEY:
    dashscope.api_key = DASHSCOPE_API_KEY

def get_text_embeddings(text: str):
    """调用 DashScope 获取文本向量"""
    if not DASHSCOPE_API_KEY:
        # 模拟向量
        return [0.1] * 1536
        
    try:
        resp = dashscope.TextEmbedding.call(
            model=dashscope.TextEmbedding.Models.text_embedding_v1,
            input=text
        )
        if resp.status_code == 200:
            return resp.output['embeddings'][0]['embedding']
        else:
            print(f"Embedding failed: {resp}")
            return [0.1] * 1536
    except Exception as e:
        print(f"Embedding error: {e}")
        return [0.1] * 1536

def cosine_similarity(vec1, vec2):
    """计算余弦相似度"""
    import math
    dot_product = sum(a*b for a,b in zip(vec1, vec2))
    norm_a = math.sqrt(sum(a*a for a in vec1))
    norm_b = math.sqrt(sum(b*b for b in vec2))
    return dot_product / (norm_a * norm_b) if norm_a and norm_b else 0.0

def retrieve_context(question_vec, db: Session, top_k=3):
    """
    简单的内存检索
    实际生产中应使用 ChromaDB/Milvus
    这里为了演示，遍历所有 StructuredResult 进行计算
    """
    results = db.query(StructuredResult).filter(StructuredResult.status == "done").all()
    
    scored_results = []
    for res in results:
        try:
            content = json.loads(res.content)
            # 将结构化数据转化为自然语言文本
            text = f"时间：{content.get('Time')}，卖方：{content.get('Seller')}，买方：{content.get('Buyer')}，价格：{content.get('Price')}，地点：{content.get('Location')}"
            
            # 实时计算向量 (实际应预先计算并存储)
            vec = get_text_embeddings(text)
            
            score = cosine_similarity(question_vec, vec)
            scored_results.append((score, text))
        except:
            continue
            
    # 按相似度排序
    scored_results.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_results[:top_k]]

def generate_answer(question: str, context_list: list):
    """调用 LLM 生成回答"""
    if not DASHSCOPE_API_KEY:
        return "由于未配置 DASHSCOPE_API_KEY，无法生成智能回答。这里是模拟回复。"
        
    context_str = "\n".join([f"- {c}" for c in context_list])
    
    prompt = f"""
    你是一个专业的古籍研究助手。请根据以下参考资料回答用户的问题。
    如果参考资料中没有相关信息，请如实告知。
    
    参考资料：
    {context_str}
    
    用户问题：{question}
    
    回答：
    """
    
    try:
        response = dashscope.Generation.call(
            model=dashscope.Generation.Models.qwen_turbo,
            prompt=prompt,
            result_format='message'
        )
        if response.status_code == 200:
            return response.output.choices[0].message.content
        else:
            return "生成回答失败，请稍后再试。"
    except Exception as e:
        return f"生成过程发生错误: {str(e)}"

def rag_pipeline(question: str, db: Session):
    """RAG 主流程"""
    # 1. 问题向量化
    q_vec = get_text_embeddings(question)
    
    # 2. 检索相关文档
    context = retrieve_context(q_vec, db)
    
    # 3. 生成回答
    answer = generate_answer(question, context)
    
    return {
        "answer": answer,
        "sources": context
    }
