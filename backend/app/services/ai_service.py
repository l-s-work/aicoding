"""
AI 服务层：OpenAI 集成、向量计算、智能推荐
"""
import json
import hashlib
import logging
from typing import Optional

import numpy as np
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import settings
from app.db.models import Product, ProductEmbedding, ChatMessage

# 日志记录器
logger = logging.getLogger(__name__)

# 聊天客户端：保持现有 OPENAI_* 配置，不影响原有对话能力
chat_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL
)

# Embedding 客户端：优先使用千问配置，对接 qwen3-vl-embedding
embedding_client = AsyncOpenAI(
    api_key=settings.embedding_api_key,
    base_url=settings.embedding_base_url
)


async def generate_embedding(text: str) -> list[float]:
    """
    生成文本的 Embedding 向量
    
    Args:
        text: 输入文本
        
    Returns:
        由具体 Embedding 模型决定的向量
    """
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Embedding 输入文本不能为空")

    try:
        response = await embedding_client.embeddings.create(
            model=settings.embedding_model,
            input=normalized_text
        )
    except Exception as exc:
        logger.exception("Embedding 调用失败，model=%s", settings.embedding_model)
        raise RuntimeError("Embedding 服务调用失败，请检查模型配置或 API Key") from exc

    if not response.data or not response.data[0].embedding:
        raise RuntimeError("Embedding 服务返回空向量")
    
    return response.data[0].embedding


async def compute_content_hash(name: str, description: str) -> str:
    """计算商品内容的 SHA-256 哈希"""
    content = f"{name}:::{description or ''}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


async def sync_product_embedding(
    db: AsyncSession,
    product_id: int,
    force: bool = False
) -> None:
    """
    同步商品的 Embedding 向量
    
    Args:
        db: 数据库会话
        product_id: 商品 ID
        force: 是否强制重新生成（忽略哈希检查）
    """
    # 查询商品
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    
    if not product:
        return
    
    # 计算内容哈希
    content_hash = await compute_content_hash(product.name, product.description or "")
    
    # 检查是否已有向量
    embedding_result = await db.execute(
        select(ProductEmbedding).where(ProductEmbedding.product_id == product_id)
    )
    existing_embedding = embedding_result.scalar_one_or_none()
    
    # 如果哈希未变化且不强制更新，则跳过
    if not force and existing_embedding and existing_embedding.content_hash == content_hash:
        return
    
    # 生成 Embedding
    text_content = f"{product.name}\n{product.description or ''}"
    embedding_vector = await generate_embedding(text_content)
    
    # 保存或更新
    if existing_embedding:
        existing_embedding.embedding = json.dumps(embedding_vector)
        existing_embedding.content_hash = content_hash
    else:
        new_embedding = ProductEmbedding(
            product_id=product_id,
            embedding=json.dumps(embedding_vector),
            content_hash=content_hash
        )
        db.add(new_embedding)
    
    await db.commit()


async def search_similar_products(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    status: str = "on_sale"
) -> list[dict]:
    """
    基于向量相似度搜索商品
    
    Args:
        db: 数据库会话
        query: 用户查询文本
        top_k: 返回前 K 个结果
        status: 商品状态筛选
        
    Returns:
        商品列表（包含相似度分数）
    """
    # 生成查询向量
    query_vector = await generate_embedding(query)
    query_array = np.array(query_vector, dtype=np.float32)
    
    # 查询所有在售商品的向量
    stmt = (
        select(Product, ProductEmbedding)
        .join(ProductEmbedding, Product.id == ProductEmbedding.product_id)
        .where(Product.status == status)
    )
    
    result = await db.execute(stmt)
    rows = result.all()
    
    if not rows:
        return []
    
    # 计算余弦相似度
    similarities = []
    
    for product, embedding in rows:
        try:
            # 解析向量
            product_vector = json.loads(embedding.embedding)
            product_array = np.array(product_vector, dtype=np.float32)
        except (json.JSONDecodeError, ValueError, TypeError):
            logger.warning("商品 %s 的 embedding 数据损坏，已跳过", product.id)
            continue

        # 切模型后可能存在历史向量维度不一致，直接跳过避免计算报错
        if product_array.shape != query_array.shape:
            logger.info(
                "商品 %s 向量维度不匹配，query=%s, product=%s，已跳过",
                product.id, query_array.shape, product_array.shape
            )
            continue
        
        # 余弦相似度
        denominator = np.linalg.norm(query_array) * np.linalg.norm(product_array)
        similarity = 0.0 if denominator == 0 else np.dot(query_array, product_array) / denominator
        
        similarities.append({
            "product": product,
            "similarity": float(similarity)
        })
    
    # 按相似度排序
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    # 返回 Top K
    return similarities[:top_k]


async def chat_with_ai(
    db: AsyncSession,
    user_id: int,
    user_message: str,
    context: Optional[dict] = None
) -> dict:
    """
    与 AI 对话（流式响应的准备工作）
    
    Args:
        db: 数据库会话
        user_id: 用户 ID
        user_message: 用户消息
        context: 前端上下文（当前页面、购物车等）
        
    Returns:
        对话结果（包含推荐商品、响应内容等）
    """
    # 保存用户消息
    user_msg = ChatMessage(
        user_id=user_id,
        role="user",
        content=user_message,
        ui_type="text"
    )
    db.add(user_msg)
    await db.commit()
    
    # 获取历史对话（最近10条）
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history = history_result.scalars().all()
    history.reverse()  # 时间正序
    
    # 构建对话历史
    messages = [
        {
            "role": "system",
            "content": (
                "你是一位专业的电商导购助手，名叫「智购小助手」。"
                "你的任务是根据用户的需求，推荐合适的商品。"
                "如果用户询问商品推荐，请使用向量搜索找到最相关的商品，"
                "然后以友好、专业的方式介绍这些商品。"
            )
        }
    ]
    
    for msg in history[-5:]:  # 最近5条
        messages.append({
            "role": msg.role,
            "content": msg.content
        })
    
    # 搜索相关商品
    similar_products = await search_similar_products(db, user_message, top_k=3)
    
    # 如果找到相关商品，添加到系统消息
    if similar_products:
        product_info = "\n\n当前系统中找到以下相关商品:\n"
        for i, item in enumerate(similar_products, 1):
            product = item["product"]
            product_info += f"{i}. {product.name} - ¥{product.price} (库存: {product.stock})\n"
            product_info += f"   描述: {product.description or '暂无描述'}\n"
        
        messages.append({
            "role": "system",
            "content": product_info
        })
    
    return {
        "messages": messages,
        "similar_products": similar_products,
        "context": context or {}
    }


async def generate_streaming_response(messages: list[dict]):
    """
    生成流式响应（SSE 生成器）
    
    Yields:
        SSE 格式的数据块
    """
    stream = await chat_client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        stream=True,
        temperature=0.7,
    )
    
    async for chunk in stream:
        if chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            yield f"data: {json.dumps({'content': content}, ensure_ascii=False)}\n\n"
    
    # 结束标记
    yield "data: [DONE]\n\n"
