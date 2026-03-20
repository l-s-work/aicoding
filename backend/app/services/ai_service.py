"""
AI 服务层：AI 对话、向量计算、智能推荐
"""
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
import logging
import re
from typing import Optional

import httpx
import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import ChatMessage, Product, ProductEmbedding, ProductEmbeddingStatus

logger = logging.getLogger(__name__)

# 聊天客户端保持现有 OpenAI 兼容配置，不影响原有聊天链路
chat_client = AsyncOpenAI(
    api_key=settings.OPENAI_API_KEY,
    base_url=settings.OPENAI_BASE_URL
)

# 兼容模式 Embedding 客户端：适用于 OpenAI 标准文本向量接口
compatible_embedding_client = AsyncOpenAI(
    api_key=settings.embedding_api_key,
    base_url=settings.embedding_base_url
)

EMBEDDING_STATUS_PENDING = "pending"
EMBEDDING_STATUS_SUCCESS = "success"
EMBEDDING_STATUS_FAILED = "failed"


def now_iso() -> str:
    """统一生成 ISO 时间字符串。"""
    return datetime.utcnow().isoformat()


def is_qwen_multimodal_embedding_model(model_name: str) -> bool:
    """
    判断当前模型是否需要走百炼多模态向量接口。

    `qwen3-vl-embedding` 不走 OpenAI 兼容 `/embeddings`，
    需要调用百炼多模态 Embedding 专用接口。
    """
    normalized_name = model_name.strip().lower()
    return (
        "vl-embedding" in normalized_name
        or normalized_name.startswith("tongyi-embedding-vision")
        or normalized_name == "multimodal-embedding-v1"
    )


def build_qwen_multimodal_payload(text: str) -> dict:
    """构造百炼多模态向量接口请求体。"""
    payload = {
        "model": settings.embedding_model,
        "input": {
            "contents": [
                {
                    "text": text,
                }
            ]
        },
        "parameters": {
            "output_type": "dense",
        },
    }

    if settings.QWEN_EMBEDDING_DIMENSION:
        payload["parameters"]["dimension"] = settings.QWEN_EMBEDDING_DIMENSION

    return payload


def extract_qwen_error_message(payload: dict, fallback: str) -> str:
    """从百炼错误响应中提取可读错误信息。"""
    code = payload.get("code")
    message = payload.get("message")
    request_id = payload.get("request_id") or payload.get("requestId")

    parts = [part for part in [code, message] if part]
    if request_id:
        parts.append(f"request_id={request_id}")

    return " | ".join(parts) if parts else fallback


async def generate_qwen_multimodal_embedding(text: str) -> list[float]:
    """
    调用百炼多模态 Embedding 接口生成向量。

    说明：
    - `qwen3-vl-embedding` 不是 OpenAI 兼容 Embedding 模型
    - 这里显式走阿里云百炼官方多模态向量接口
    """
    if not settings.embedding_api_key:
        raise RuntimeError("未配置千问 Embedding API Key")

    payload = build_qwen_multimodal_payload(text)
    headers = {
        "Authorization": f"Bearer {settings.embedding_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            settings.QWEN_MULTIMODAL_EMBEDDING_URL,
            headers=headers,
            json=payload,
        )

    try:
        response_payload = response.json()
    except json.JSONDecodeError:
        response_payload = {}

    if response.status_code >= 400:
        detail = extract_qwen_error_message(
            response_payload,
            fallback=f"HTTP {response.status_code}"
        )
        raise RuntimeError(f"千问 Embedding 调用失败: {detail}")

    embedding_list = response_payload.get("output", {}).get("embeddings", [])
    if not embedding_list:
        raise RuntimeError("千问 Embedding 服务返回空结果")

    embedding_vector = embedding_list[0].get("embedding")
    if not embedding_vector:
        raise RuntimeError("千问 Embedding 服务未返回有效向量")

    return embedding_vector


async def generate_embedding(text: str) -> list[float]:
    """
    生成文本 Embedding 向量。

    - `qwen3-vl-embedding` 走百炼多模态接口
    - 其他模型沿用 OpenAI 兼容 `/embeddings`
    """
    normalized_text = text.strip()
    if not normalized_text:
        raise ValueError("Embedding 输入文本不能为空")

    if is_qwen_multimodal_embedding_model(settings.embedding_model):
        try:
            return await generate_qwen_multimodal_embedding(normalized_text)
        except Exception as exc:
            logger.exception("千问 Embedding 调用失败，model=%s", settings.embedding_model)
            raise RuntimeError(str(exc)) from exc

    try:
        response = await compatible_embedding_client.embeddings.create(
            model=settings.embedding_model,
            input=normalized_text
        )
    except Exception as exc:
        logger.exception("兼容模式 Embedding 调用失败，model=%s", settings.embedding_model)
        raise RuntimeError("Embedding 服务调用失败，请检查模型配置或 API Key") from exc

    if not response.data or not response.data[0].embedding:
        raise RuntimeError("Embedding 服务返回空向量")

    return response.data[0].embedding


async def compute_content_hash(name: str, description: str) -> str:
    """计算商品内容哈希，用于避免重复生成向量。"""
    content = f"{name}:::{description or ''}"
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_product_embedding_text(product: Product) -> str:
    """
    构造商品向量化文本。
    当前保持轻量，仅使用商品名称与描述。
    """
    return f"{product.name}\n{product.description or ''}".strip()


def build_product_search_text(product: Product) -> str:
    """
    构造轻量文本检索内容。
    即使向量化失败，也能通过名称、描述、标签做兜底推荐。
    """
    raw_tags = product.tags or ""
    tags_text = raw_tags

    try:
        parsed_tags = json.loads(raw_tags) if raw_tags else []
        if isinstance(parsed_tags, list):
            tags_text = " ".join(str(tag) for tag in parsed_tags)
    except (json.JSONDecodeError, TypeError):
        tags_text = raw_tags

    return " ".join(
        part.strip()
        for part in [product.name, product.description or "", tags_text]
        if part and part.strip()
    )


def normalize_similarity_text(text: str) -> str:
    """清洗文本，保留中英文与数字。"""
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", text.lower())
    return " ".join(normalized.split())


def build_similarity_tokens(text: str) -> set[str]:
    """
    生成轻量检索 token。
    中文额外补充 2-gram，降低无空格中文匹配失准。
    """
    normalized = normalize_similarity_text(text)
    if not normalized:
        return set()

    parts = normalized.split()
    tokens = set(parts)

    compact = normalized.replace(" ", "")
    if len(compact) == 1:
        tokens.add(compact)
    elif len(compact) > 1:
        tokens.update(compact[index:index + 2] for index in range(len(compact) - 1))

    return {token for token in tokens if token}


def compute_text_similarity(query: str, candidate: str) -> float:
    """
    计算轻量文本相似度。
    用于无向量或向量服务异常时的兜底推荐。
    """
    query_text = normalize_similarity_text(query)
    candidate_text = normalize_similarity_text(candidate)
    if not query_text or not candidate_text:
        return 0.0

    query_tokens = build_similarity_tokens(query_text)
    candidate_tokens = build_similarity_tokens(candidate_text)

    overlap_ratio = 0.0
    if query_tokens:
        overlap_ratio = len(query_tokens & candidate_tokens) / len(query_tokens)

    sequence_ratio = SequenceMatcher(None, query_text, candidate_text).ratio()
    substring_bonus = 0.15 if query_text in candidate_text else 0.0

    score = overlap_ratio * 0.55 + sequence_ratio * 0.45 + substring_bonus
    return min(1.0, score)


async def upsert_embedding_status(
    db: AsyncSession,
    product_id: int,
    status: str,
    last_error: Optional[str] = None,
    increment_retry: bool = False
) -> ProductEmbeddingStatus:
    """
    更新商品向量化状态。
    错误信息会截断，避免单条异常撑大 SQLite 记录。
    """
    result = await db.execute(
        select(ProductEmbeddingStatus).where(ProductEmbeddingStatus.product_id == product_id)
    )
    status_record = result.scalar_one_or_none()

    if not status_record:
        status_record = ProductEmbeddingStatus(product_id=product_id)
        db.add(status_record)

    status_record.status = status
    status_record.last_error = (last_error or None)
    if status_record.last_error and len(status_record.last_error) > 500:
        status_record.last_error = status_record.last_error[:500]
    status_record.updated_at = now_iso()

    if increment_retry:
        status_record.retry_count += 1

    if status == EMBEDDING_STATUS_SUCCESS:
        status_record.last_error = None
        status_record.last_success_at = status_record.updated_at

    return status_record


async def sync_product_embedding(
    db: AsyncSession,
    product_id: int,
    force: bool = False
) -> bool:
    """
    同步商品 Embedding。

    Returns:
        是否真的生成/更新了向量
    """
    result = await db.execute(
        select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()

    if not product:
        return False

    await upsert_embedding_status(
        db,
        product_id=product_id,
        status=EMBEDDING_STATUS_PENDING,
        increment_retry=True
    )
    await db.commit()

    content_hash = await compute_content_hash(product.name, product.description or "")

    embedding_result = await db.execute(
        select(ProductEmbedding).where(ProductEmbedding.product_id == product_id)
    )
    existing_embedding = embedding_result.scalar_one_or_none()

    if not force and existing_embedding and existing_embedding.content_hash == content_hash:
        await upsert_embedding_status(
            db,
            product_id=product_id,
            status=EMBEDDING_STATUS_SUCCESS,
        )
        await db.commit()
        return False

    text_content = build_product_embedding_text(product)
    try:
        embedding_vector = await generate_embedding(text_content)
    except Exception as exc:
        await upsert_embedding_status(
            db,
            product_id=product_id,
            status=EMBEDDING_STATUS_FAILED,
            last_error=str(exc)
        )
        await db.commit()
        raise

    if existing_embedding:
        existing_embedding.embedding = json.dumps(embedding_vector, ensure_ascii=False)
        existing_embedding.content_hash = content_hash
        existing_embedding.updated_at = now_iso()
    else:
        db.add(
            ProductEmbedding(
                product_id=product_id,
                embedding=json.dumps(embedding_vector, ensure_ascii=False),
                content_hash=content_hash,
                updated_at=now_iso()
            )
        )

    await upsert_embedding_status(
        db,
        product_id=product_id,
        status=EMBEDDING_STATUS_SUCCESS,
    )
    await db.commit()
    return True


async def trigger_product_embedding_sync(product_id: int, force: bool = False) -> None:
    """
    后台异步执行商品向量化。
    使用独立数据库会话，避免复用已经关闭的请求会话。
    """
    async with AsyncSessionLocal() as db:
        try:
            await sync_product_embedding(db, product_id=product_id, force=force)
        except Exception:
            logger.exception("后台商品向量化失败，product_id=%s", product_id)


def compute_vector_similarity(
    query_array: np.ndarray,
    embedding_json: str,
    product_id: int
) -> Optional[float]:
    """计算余弦相似度；异常时返回 None 以触发文本降级。"""
    try:
        product_vector = json.loads(embedding_json)
        product_array = np.array(product_vector, dtype=np.float32)
    except (json.JSONDecodeError, ValueError, TypeError):
        logger.warning("商品 %s 的 embedding 数据损坏，已回退到文本推荐", product_id)
        return None

    if product_array.shape != query_array.shape:
        logger.info(
            "商品 %s 向量维度不匹配，query=%s, product=%s，已回退到文本推荐",
            product_id, query_array.shape, product_array.shape
        )
        return None

    denominator = np.linalg.norm(query_array) * np.linalg.norm(product_array)
    if denominator == 0:
        return 0.0

    return float(np.dot(query_array, product_array) / denominator)


async def search_similar_products(
    db: AsyncSession,
    query: str,
    top_k: int = 5,
    status: str = "on_sale"
) -> list[dict]:
    """
    搜索相似商品。

    优先使用向量相似度；若向量缺失或 Embedding 服务失败，
    自动降级到轻量文本相似，保证推荐链路可用。
    """
    stmt = (
        select(Product, ProductEmbedding)
        .outerjoin(ProductEmbedding, Product.id == ProductEmbedding.product_id)
        .where(Product.status == status)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return []

    query_array: Optional[np.ndarray] = None
    try:
        query_vector = await generate_embedding(query)
        query_array = np.array(query_vector, dtype=np.float32)
    except Exception as exc:
        logger.warning("查询向量生成失败，已降级为文本推荐: %s", exc)

    similarities = []

    for product, embedding in rows:
        fallback_similarity = compute_text_similarity(query, build_product_search_text(product))

        vector_similarity: Optional[float] = None
        if query_array is not None and embedding is not None:
            vector_similarity = compute_vector_similarity(query_array, embedding.embedding, product.id)

        if vector_similarity is None:
            similarity = fallback_similarity
            source = "text"
        else:
            similarity = max(vector_similarity * 0.8 + fallback_similarity * 0.2, fallback_similarity)
            source = "vector"

        if similarity <= 0:
            continue

        similarities.append({
            "product": product,
            "similarity": float(similarity),
            "source": source,
        })

    similarities.sort(key=lambda item: item["similarity"], reverse=True)
    return similarities[:top_k]


async def chat_with_ai(
    db: AsyncSession,
    user_id: int,
    user_message: str,
    context: Optional[dict] = None
) -> dict:
    """
    与 AI 对话的准备步骤。
    会先组装历史消息，再尝试检索相关商品。
    """
    user_msg = ChatMessage(
        user_id=user_id,
        role="user",
        content=user_message,
        ui_type="text"
    )
    db.add(user_msg)
    await db.commit()

    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(10)
    )
    history = history_result.scalars().all()
    history.reverse()

    messages = [
        {
            "role": "system",
            "content": (
                "你是一位专业的电商导购助手，名叫「智购小助手」。"
                "你的任务是根据用户的需求，推荐合适的商品。"
                "如果用户询问商品推荐，请优先使用系统提供的候选商品，"
                "然后以友好、专业的方式介绍这些商品。"
            )
        }
    ]

    for msg in history[-5:]:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    try:
        similar_products = await search_similar_products(db, user_message, top_k=3)
    except Exception:
        logger.exception("商品推荐检索失败，已降级为纯聊天模式")
        similar_products = []

    if similar_products:
        product_info = "\n\n当前系统中找到以下相关商品:\n"
        for index, item in enumerate(similar_products, 1):
            product = item["product"]
            product_info += f"{index}. {product.name} - ¥{product.price} (库存: {product.stock})\n"
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
    生成流式响应（SSE）。
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

    yield "data: [DONE]\n\n"
