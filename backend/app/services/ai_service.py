"""
AI 服务层：AI 对话、向量计算、智能推荐、C 端业务上下文编排
"""
from datetime import datetime
from difflib import SequenceMatcher
import hashlib
import json
import logging
import re
from typing import Any, Optional

import httpx
import numpy as np
from openai import AsyncOpenAI
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.database import AsyncSessionLocal
from app.db.models import ChatMessage, Order, OrderItem, Product, ProductEmbedding, ProductEmbeddingStatus, User, UserAddress

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

PRODUCT_HINT_KEYWORDS = (
    "商品", "产品", "推荐", "类似", "同款", "同类",
    "有没有", "适合", "怎么样", "值得买", "质量", "功能", "参数", "库存", "价格",
)
ORDER_HINT_KEYWORDS = (
    "订单", "下单", "物流", "发货", "收货", "支付", "退款", "退货", "催单", "订单号",
)
ORDER_LIST_KEYWORDS = (
    "全部订单",
    "所有订单",
    "订单列表",
    "订单记录",
    "最近订单",
    "我的订单有哪些",
    "有哪些订单",
    "订单有多少",
    "多少订单",
    "几笔订单",
    "查看订单",
)
PURCHASE_HISTORY_KEYWORDS = (
    "历史下单商品",
    "全部历史下单商品",
    "历史订单商品",
    "历史购买商品",
    "购买过的商品",
    "买过的商品",
    "买过哪些商品",
    "下单商品",
    "历史下单过的商品",
)
ADDRESS_HINT_KEYWORDS = (
    "地址", "收货地址", "收件", "默认地址", "联系人", "手机号", "电话",
)
ACCOUNT_HINT_KEYWORDS = (
    "账号", "账户", "个人信息", "用户名", "邮箱", "我的资料", "账号信息",
)
PRODUCT_RECOMMEND_KEYWORDS = ("推荐", "类似", "同款", "同类", "相近", "替代")
PRODUCT_DISCOVERY_KEYWORDS = ("有没有", "有吗", "想买", "想要", "找", "看看", "来点", "求", "需要")
PRODUCT_FOLLOW_UP_KEYWORDS = ("换成", "改成", "换个", "换款", "改一下", "换一下", "换耳机", "换音响")
PRODUCT_REFERENCE_KEYWORDS = ("这件", "这个", "它", "当前商品", "该商品", "这款")
GENERIC_SIMILARITY_PATTERNS = (
    "类似商品", "类似的商品", "同类商品", "同款商品", "相似商品", "推荐一些类似", "推荐点类似",
)
ORDER_REFERENCE_KEYWORDS = ("这个订单", "该订单", "这笔订单", "这单", "它")
ADDRESS_REFERENCE_KEYWORDS = ("这个地址", "该地址", "这个收货地址", "这个收件地址", "它")
DEFAULT_ADDRESS_KEYWORDS = ("默认地址", "默认收货地址", "常用地址")
GENERIC_AMBIGUOUS_KEYWORDS = ("这个", "这件", "这个订单", "这个地址", "它", "那个")
PRODUCT_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "手机": ("手机", "iphone", "安卓", "折叠屏"),
    "电脑": ("电脑", "笔记本", "轻薄本", "游戏本", "macbook"),
    "平板": ("平板", "pad"),
    "耳机": ("耳机", "蓝牙耳机", "头戴"),
    "音响": ("音响", "音箱", "speaker"),
    "手表": ("手表", "智能表", "watch"),
    "游戏机": ("游戏机", "主机", "ps5", "switch", "xbox"),
}


def now_iso() -> str:
    """统一生成 ISO 时间字符串。"""
    return datetime.utcnow().isoformat()


def order_load_options():
    """订单详情预加载，避免异步懒加载触发 MissingGreenlet。"""
    return (
        selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.category),
    )


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


def safe_json_loads(raw_text: str | None, fallback: Any) -> Any:
    """轻量 JSON 解析工具，避免单条脏数据中断 AI 链路。"""
    if not raw_text:
        return fallback
    try:
        return json.loads(raw_text)
    except (json.JSONDecodeError, TypeError):
        return fallback


def trim_text(text: str | None, limit: int = 120) -> str:
    """限制长文本长度，避免把整页描述原样塞进 Prompt。"""
    normalized = (text or "").strip()
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[:limit]}..."


def parse_receiver_info(receiver_info: str) -> dict[str, Any]:
    """解析订单中的地址快照 JSON。"""
    data = safe_json_loads(receiver_info, {})
    if isinstance(data, dict):
        return data
    return {}


def build_full_address(address: UserAddress | dict[str, Any]) -> str:
    """拼接地址全量字符串，用于卡片回显与 Prompt 提示。"""
    if isinstance(address, dict):
        parts = [
            str(address.get("province") or "").strip(),
            str(address.get("city") or "").strip(),
            str(address.get("district") or "").strip(),
            str(address.get("detail_address") or "").strip(),
        ]
    else:
        parts = [
            address.province.strip(),
            address.city.strip(),
            address.district.strip(),
            address.detail_address.strip(),
        ]
    return " ".join(part for part in parts if part)


def serialize_product_summary(product: Product) -> dict[str, Any]:
    """给模型使用的商品摘要，字段尽量精简。"""
    tags = safe_json_loads(product.tags, [])
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
        "status": product.status,
        "category": getattr(product.category, "name", None),
        "description": trim_text(product.description, 180),
        "tags": tags if isinstance(tags, list) else [],
    }


def serialize_product_card(
    product: Product,
    *,
    similarity: Optional[float] = None,
    reason: Optional[str] = None,
    source: str = "context",
) -> dict[str, Any]:
    """前端商品卡片结构。"""
    card = {
        "type": "product",
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
        "status": product.status,
        "image_url": product.image_url,
        "description": trim_text(product.description, 100),
        "category_name": getattr(product.category, "name", None),
        "route": f"/product/{product.id}",
        "source": source,
        "reason": reason,
    }
    if similarity is not None:
        card["similarity"] = round(float(similarity), 4)
    return card


def serialize_order_item_snapshot(item: OrderItem) -> dict[str, Any]:
    """订单明细快照，附带商品分类，便于模型和前端同时理解。"""
    product = getattr(item, "product", None)
    category_name = getattr(getattr(product, "category", None), "name", None)
    return {
        "product_id": item.product_id,
        "product_name": item.product_name,
        "category_name": category_name,
        "buy_price": item.buy_price,
        "quantity": item.quantity,
    }


def serialize_order_summary(order: Order) -> dict[str, Any]:
    """给模型使用的订单摘要。"""
    receiver_info = parse_receiver_info(order.receiver_info)
    return {
        "id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "total_amount": order.total_amount,
        "created_at": order.created_at,
        "receiver_name": receiver_info.get("receiver_name"),
        "address": build_full_address(receiver_info),
        "items": [serialize_order_item_snapshot(item) for item in order.items[:5]],
    }


def serialize_order_card(order: Order, *, reason: Optional[str] = None) -> dict[str, Any]:
    """前端订单卡片结构。"""
    receiver_info = parse_receiver_info(order.receiver_info)
    return {
        "type": "order",
        "id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "total_amount": order.total_amount,
        "created_at": order.created_at,
        "receiver_name": receiver_info.get("receiver_name"),
        "phone": receiver_info.get("phone"),
        "address": build_full_address(receiver_info),
        "items": [
            {
                **serialize_order_item_snapshot(item),
                "route": f"/product/{item.product_id}",
            }
            for item in order.items[:5]
        ],
        "route": f"/orders/{order.id}",
        "reason": reason,
    }


def serialize_address_summary(address: UserAddress) -> dict[str, Any]:
    """给模型使用的地址摘要。"""
    return {
        "id": address.id,
        "receiver_name": address.receiver_name,
        "phone": address.phone,
        "is_default": bool(address.is_default),
        "full_address": build_full_address(address),
    }


def serialize_address_card(address: UserAddress, *, reason: Optional[str] = None) -> dict[str, Any]:
    """前端地址卡片结构。"""
    return {
        "type": "address",
        "id": address.id,
        "receiver_name": address.receiver_name,
        "phone": address.phone,
        "province": address.province,
        "city": address.city,
        "district": address.district,
        "detail_address": address.detail_address,
        "full_address": build_full_address(address),
        "is_default": bool(address.is_default),
        "reason": reason,
    }


def serialize_account_summary(user: User) -> dict[str, Any]:
    """给模型使用的账号摘要。"""
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
    }


def serialize_account_card(user: User, *, reason: Optional[str] = None) -> dict[str, Any]:
    """前端账号卡片结构。"""
    return {
        "type": "account",
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "created_at": user.created_at,
        "reason": reason,
    }


def serialize_context_card(content: dict[str, Any]) -> dict[str, Any]:
    """兜底的说明型卡片。"""
    return {
        "type": "info",
        **content,
    }


def has_any_keyword(message: str, keywords: tuple[str, ...]) -> bool:
    """轻量关键词判断。"""
    return any(keyword in message for keyword in keywords)


def infer_intents(user_message: str, context: dict[str, Any]) -> set[str]:
    """
    使用轻量规则判断用户问题命中哪些业务域。

    设计原则：
    - 尽量只做召回，不做重分类，避免因为规则太严导致上下文缺失
    - 最终回答仍交给 LLM，根据后端提供的业务快照组织自然语言
    """
    message = (user_message or "").strip().lower()
    intents: set[str] = set()

    if has_any_keyword(message, PRODUCT_HINT_KEYWORDS):
        intents.add("product")
    elif bool(extract_product_request_constraints(user_message).get("categories")):
        # “音响呢”“换成耳机”这类短句可能没有“推荐/商品”等显式关键词，
        # 但已经带了明确品类，应视作商品咨询/推荐意图。
        intents.add("product")
    if has_any_keyword(message, ORDER_HINT_KEYWORDS):
        intents.add("order")
    if has_any_keyword(message, ADDRESS_HINT_KEYWORDS):
        intents.add("address")
    if has_any_keyword(message, ACCOUNT_HINT_KEYWORDS):
        intents.add("account")

    if context.get("page_type") == "product" and has_any_keyword(message, PRODUCT_REFERENCE_KEYWORDS):
        intents.add("product")
    if context.get("page_type") in {"orders", "order_detail"} and has_any_keyword(message, ORDER_REFERENCE_KEYWORDS):
        intents.add("order")

    return intents


def is_order_list_request(user_message: str) -> bool:
    """判断用户是否在询问订单列表，而不是单笔订单。"""
    message = (user_message or "").strip().lower()
    compact_message = re.sub(r"\s+", "", message)
    if has_any_keyword(compact_message, ORDER_LIST_KEYWORDS):
        return True

    if "订单" not in message:
        return False

    return any(keyword in message for keyword in ("有哪些", "全部", "所有", "列表", "最近", "多少", "几笔", "记录"))


def is_purchase_history_request(user_message: str) -> bool:
    """判断用户是否在询问全部历史下单商品。"""
    message = (user_message or "").strip().lower()
    compact_message = re.sub(r"\s+", "", message)
    if has_any_keyword(compact_message, PURCHASE_HISTORY_KEYWORDS):
        return True

    return (
        ("买过" in message or "下单" in message or "购买过" in message)
        and "商品" in message
    )


def should_recommend_products(user_message: str) -> bool:
    """判断用户是否在要推荐、找相似款或购物建议。"""
    message = (user_message or "").strip().lower()
    if has_any_keyword(message, PRODUCT_RECOMMEND_KEYWORDS):
        return True

    constraints = extract_product_request_constraints(user_message)
    return bool(constraints.get("categories")) and (
        has_any_keyword(message, PRODUCT_DISCOVERY_KEYWORDS)
        or has_any_keyword(message, PRODUCT_FOLLOW_UP_KEYWORDS)
    )


def is_product_follow_up_request(user_message: str, product_request: dict[str, Any]) -> bool:
    """判断当前问题是否像“换成音响”这类基于上一轮条件继续筛选的追问。"""
    if not bool(product_request.get("categories")):
        return False

    message = (user_message or "").strip().lower()
    if has_any_keyword(message, PRODUCT_FOLLOW_UP_KEYWORDS):
        return True

    compact_message = re.sub(r"\s+", "", message)
    return len(compact_message) <= 12 and compact_message.endswith(("呢", "吗", "吧"))


def merge_product_request(base_request: dict[str, Any], fallback_request: dict[str, Any]) -> dict[str, Any]:
    """把当前轮缺失的预算/数量信息从上一轮补齐，但优先保留当前轮显式条件。"""
    merged_categories = base_request.get("categories") or fallback_request.get("categories") or []

    return {
        "requested_count": base_request.get("requested_count") or fallback_request.get("requested_count"),
        "price_min": base_request.get("price_min") if base_request.get("price_min") is not None else fallback_request.get("price_min"),
        "price_max": base_request.get("price_max") if base_request.get("price_max") is not None else fallback_request.get("price_max"),
        "categories": merged_categories,
    }


def extract_recent_product_request_from_history(
    history: list[ChatMessage],
    current_user_message: str,
) -> dict[str, Any] | None:
    """从最近用户消息里恢复上一轮商品筛选条件，用于承接“换成音响”这类追问。"""
    skipped_current_message = False

    for msg in reversed(history):
        if msg.role != "user":
            continue

        if not skipped_current_message and msg.content == current_user_message:
            skipped_current_message = True
            continue

        if not should_recommend_products(msg.content):
            continue

        constraints = extract_product_request_constraints(msg.content)
        if has_product_constraints(constraints):
            return constraints

    return None


def should_anchor_product_recommendation(
    user_message: str,
    context: dict[str, Any],
    product_request: dict[str, Any],
) -> bool:
    """判断本轮商品推荐是否应该锚定到某个参考商品，而不是纯按品类/预算筛选。"""
    if not should_recommend_products(user_message):
        return False

    message = (user_message or "").strip().lower()
    if is_generic_similar_product_request(user_message):
        return True
    if has_any_keyword(message, PRODUCT_REFERENCE_KEYWORDS):
        return True

    # 商品详情页里的泛推荐可以沿用当前商品做相似推荐；
    # 但一旦用户明确给了品类约束（如“音响”“耳机”），就不再沿用旧商品，避免上下文串味。
    return context.get("page_type") == "product" and not bool(product_request.get("categories"))


def normalize_budget_value(raw_value: str, full_segment: str, *, counterpart: float | None = None) -> int | None:
    """把 `3k`、`3千`、`0.5万`、`3-5000` 这类预算数字归一成元。"""
    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    normalized_segment = full_segment.lower()
    if "万" in normalized_segment:
        value *= 10000
    elif "k" in normalized_segment or "千" in normalized_segment:
        value *= 1000
    elif value < 10 and counterpart is not None and counterpart >= 1000:
        # 兼容“3-5000 的手机”这类省略写法，按 3000-5000 处理。
        value *= 1000

    return int(round(value))


def extract_product_request_constraints(user_message: str) -> dict[str, Any]:
    """提取商品推荐里的硬约束：预算、数量、品类。"""
    message = (user_message or "").strip()
    normalized_message = message.lower()
    constraints: dict[str, Any] = {
        "requested_count": None,
        "price_min": None,
        "price_max": None,
        "categories": [],
    }

    count_match = re.search(r"(\d+)\s*(?:个|款|部|台)", message)
    if count_match:
        requested_count = int(count_match.group(1))
        if 1 <= requested_count <= 10:
            constraints["requested_count"] = requested_count

    range_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|千|万|元|块)?\s*[-~～到至]\s*(\d+(?:\.\d+)?)\s*(?:k|千|万|元|块)?", normalized_message)
    if range_match:
        lower_raw = range_match.group(1)
        upper_raw = range_match.group(2)
        upper_probe = float(upper_raw)
        price_min = normalize_budget_value(lower_raw, range_match.group(0), counterpart=upper_probe)
        price_max = normalize_budget_value(upper_raw, range_match.group(0))
        if price_min is not None and price_max is not None:
            constraints["price_min"] = min(price_min, price_max)
            constraints["price_max"] = max(price_min, price_max)
    else:
        max_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|千|万|元|块)?\s*(?:以内|以下|不超过|不要超过|最多)", normalized_message)
        min_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:k|千|万|元|块)?\s*(?:以上|起|不少于|至少)", normalized_message)
        if max_match:
            constraints["price_max"] = normalize_budget_value(max_match.group(1), max_match.group(0))
        if min_match:
            constraints["price_min"] = normalize_budget_value(min_match.group(1), min_match.group(0))

    categories: list[str] = []
    for category, aliases in PRODUCT_CATEGORY_KEYWORDS.items():
        if any(alias in normalized_message for alias in aliases):
            categories.append(category)
    constraints["categories"] = categories

    return constraints


def has_product_constraints(constraints: dict[str, Any]) -> bool:
    """判断本轮推荐是否带有需要强约束的条件。"""
    return bool(
        constraints.get("categories")
        or constraints.get("requested_count")
        or constraints.get("price_min") is not None
        or constraints.get("price_max") is not None
    )


def product_matches_constraints(product: Product, constraints: dict[str, Any]) -> bool:
    """按用户明确提出的预算/品类硬过滤推荐结果。"""
    price_min = constraints.get("price_min")
    price_max = constraints.get("price_max")
    if price_min is not None and product.price < float(price_min):
        return False
    if price_max is not None and product.price > float(price_max):
        return False

    categories = constraints.get("categories") or []
    if not categories:
        return True

    raw_tags = safe_json_loads(product.tags, [])
    tag_text = " ".join(str(tag) for tag in raw_tags) if isinstance(raw_tags, list) else str(product.tags or "")
    haystack = " ".join(
        part.lower()
        for part in [
            product.name,
            product.description or "",
            getattr(product.category, "name", None) or "",
            tag_text,
        ]
        if part
    )

    for category in categories:
        aliases = PRODUCT_CATEGORY_KEYWORDS.get(category, (category,))
        if any(alias in haystack for alias in aliases):
            return True
    return False


def filter_similar_products_by_constraints(
    similar_products: list[dict[str, Any]],
    constraints: dict[str, Any],
) -> list[dict[str, Any]]:
    """先做硬过滤，再按用户要求的数量截断。"""
    filtered = [
        item
        for item in similar_products
        if isinstance(item.get("product"), Product) and product_matches_constraints(item["product"], constraints)
    ]

    requested_count = constraints.get("requested_count")
    if isinstance(requested_count, int) and requested_count > 0:
        return filtered[:requested_count]
    return filtered


def build_product_constraint_summary(constraints: dict[str, Any]) -> str:
    """把预算/品类约束拼成用户可读描述。"""
    parts: list[str] = []

    categories = constraints.get("categories") or []
    if categories:
        parts.append("、".join(categories))

    price_min = constraints.get("price_min")
    price_max = constraints.get("price_max")
    if price_min is not None and price_max is not None:
        parts.append(f"{int(price_min)}-{int(price_max)} 元")
    elif price_min is not None:
        parts.append(f"{int(price_min)} 元以上")
    elif price_max is not None:
        parts.append(f"{int(price_max)} 元以内")

    requested_count = constraints.get("requested_count")
    if isinstance(requested_count, int) and requested_count > 0:
        parts.append(f"{requested_count} 个")

    return "，".join(parts)


def build_no_matching_products_answer(constraints: dict[str, Any]) -> str:
    """当没有任何商品命中硬约束时，直接给出确定性回答，避免模型乱荐。"""
    summary = build_product_constraint_summary(constraints)
    if summary:
        return f"我这边暂时没有筛到符合“{summary}”条件的在售商品，所以先不乱推荐其他品类给你。你可以放宽预算或换个品类，我再继续帮你筛。"
    return "我这边暂时没有筛到符合条件的在售商品，所以先不乱推荐其他品类给你。你可以补充预算、数量或品类，我再继续帮你筛。"


def build_order_list_answer(order_count: int, shown_count: int) -> str:
    """当用户问订单列表时，给出确定性的摘要回答。"""
    if order_count <= 0:
        return "你现在还没有订单。"
    if shown_count <= 0:
        return f"我查到你一共有 {order_count} 笔订单，但当前没有可展示的订单。"
    if order_count <= shown_count:
        return f"你一共有 {order_count} 笔订单，我已经把全部订单都展示出来了。"
    return f"你一共有 {order_count} 笔订单，我先给你展示最近 {shown_count} 笔，方便你快速查看。"


def build_purchase_history_snapshot(orders: list[Order]) -> tuple[list[dict[str, Any]], str]:
    """把全部历史订单汇总成按商品去重的购买清单。"""
    aggregated: dict[int, dict[str, Any]] = {}
    total_quantity = 0

    for order in orders:
        for item in order.items:
            product = getattr(item, "product", None)
            if product is None:
                continue

            record = aggregated.get(product.id)
            if record is None:
                record = {
                    "product": product,
                    "quantity": 0,
                    "order_count": 0,
                    "last_order_at": order.created_at,
                    "last_order_no": order.order_no,
                }
                aggregated[product.id] = record

            record["quantity"] += int(item.quantity or 0)
            record["order_count"] += 1
            total_quantity += int(item.quantity or 0)

            current_last = str(record["last_order_at"])
            incoming_last = str(order.created_at)
            if incoming_last > current_last:
                record["last_order_at"] = order.created_at
                record["last_order_no"] = order.order_no

    sorted_records = sorted(
        aggregated.values(),
        key=lambda item: (str(item["last_order_at"]), int(getattr(item["product"], "id", 0))),
        reverse=True,
    )

    cards: list[dict[str, Any]] = []
    lines: list[str] = []
    for index, record in enumerate(sorted_records, start=1):
        product = record["product"]
        category_name = getattr(getattr(product, "category", None), "name", None)
        quantity = int(record["quantity"])
        order_count = int(record["order_count"])
        lines.append(
            f"{index}. {product.name} x{quantity}"
            + (f"（{category_name}）" if category_name else "")
        )
        cards.append(
            serialize_product_card(
                product,
                reason=f"历史下单 {order_count} 笔，共 {quantity} 件，最近一次下单 {record['last_order_no']}",
            )
        )

    summary = (
        f"你一共下过 {len(orders)} 笔订单，"
        f"买过 {len(sorted_records)} 种不同商品，"
        f"累计 {total_quantity} 件。"
    )
    if lines:
        summary = summary + "\n" + "\n".join(lines)
    return cards, summary


def extract_order_reference(user_message: str) -> str | None:
    """从用户问题里提取订单 ID 或订单号。"""
    message = (user_message or "").strip()

    pattern = re.search(r"(?:订单号|单号|订单)\s*[:：#]?\s*([A-Za-z0-9\-]{4,})", message)
    if pattern:
        return pattern.group(1)

    numeric_match = re.search(r"\b(\d{4,})\b", message)
    if numeric_match:
        return numeric_match.group(1)

    return None


def is_generic_similar_product_request(user_message: str) -> bool:
    """
    判断是否属于“要找类似商品，但没说明参考对象”的问法。

    例如：
    - 给我推荐一些类似商品
    - 有没有同款推荐
    """
    message = (user_message or "").strip().lower()
    return should_recommend_products(message) and (
        any(pattern in message for pattern in GENERIC_SIMILARITY_PATTERNS)
        or any(keyword in message for keyword in PRODUCT_REFERENCE_KEYWORDS)
    )


def build_product_reference_clarification() -> str:
    """当系统无法判断“类似推荐”的参考商品时，向用户追问。"""
    return (
        "你想参考哪件商品来找类似推荐？"
        "可以直接告诉我商品名，"
        "例如“给我推荐类似 XX 的商品”；"
        "如果你是想参考刚刚聊过的某件商品，也可以直接把商品名再发我一次。"
    )


def build_order_reference_clarification() -> str:
    """当系统无法判断用户指的是哪笔订单时，向用户追问。"""
    return (
        "你想咨询哪一笔订单？"
        "可以直接告诉我订单号，"
        "例如“帮我看看订单号 202603200001 的状态”；"
        "如果你想看最近订单或全部订单，也可以直接说“帮我看看最近订单”或“帮我看全部订单”。"
    )


def build_address_reference_clarification() -> str:
    """当系统无法判断用户指的是哪个地址时，向用户追问。"""
    return (
        "你想看哪一个收货地址？"
        "可以直接告诉我是“默认地址”，"
        "或者说出收货人姓名、手机号后四位等信息，我再帮你定位。"
    )


def build_generic_clarification() -> str:
    """当用户问题存在明显代词但业务域无法判断时，统一追问。"""
    return (
        "我还不能确定你具体想问的是商品、订单、地址还是账号信息。"
        "可以再补充一下对象吗？"
        "例如商品名、订单号，或者直接说“默认地址”“我的账号信息”。"
    )


def is_singular_order_request(user_message: str) -> bool:
    """判断用户是否在询问某一笔具体订单。"""
    message = (user_message or "").strip().lower()
    if is_order_list_request(message):
        return False
    return (
        any(keyword in message for keyword in ORDER_REFERENCE_KEYWORDS)
        or ("订单" in message and any(keyword in message for keyword in ("状态", "详情", "地址", "收货信息", "物流")))
    )


def is_singular_address_request(user_message: str) -> bool:
    """判断用户是否在询问某一个具体地址。"""
    message = (user_message or "").strip().lower()
    return any(keyword in message for keyword in ADDRESS_REFERENCE_KEYWORDS)


def is_default_address_request(user_message: str) -> bool:
    """判断用户是否明确问默认地址。"""
    message = (user_message or "").strip().lower()
    return any(keyword in message for keyword in DEFAULT_ADDRESS_KEYWORDS)


def needs_generic_clarification(intents: set[str], user_message: str) -> bool:
    """当问题只有模糊代词但没有明确业务域时，统一追问。"""
    message = (user_message or "").strip().lower()
    if intents:
        return False
    return any(keyword in message for keyword in GENERIC_AMBIGUOUS_KEYWORDS)


def extract_latest_typed_card_from_history(history: list[ChatMessage], card_type: str) -> dict[str, Any] | None:
    """
    从最近对话里提取最后一次出现的指定类型卡片。

    设计说明：
    - 商品/订单/地址问答都会把结构化卡片持久化到 assistant payload
    - 因此可从最近卡片里恢复“上一轮在聊谁”
    """
    for msg in reversed(history):
        if msg.role != "assistant" or not msg.payload:
            continue

        payload = safe_json_loads(msg.payload, [])
        if not isinstance(payload, list):
            continue

        for item in payload:
            if not isinstance(item, dict):
                continue
            if item.get("type") == card_type and isinstance(item.get("id"), int):
                return item

            # 兼容旧版 product_cards 结构
            if card_type == "product" and "type" not in item and isinstance(item.get("id"), int) and isinstance(item.get("name"), str):
                return {
                    "type": "product",
                    "id": item["id"],
                    "name": item["name"],
                }

    return None


def build_clarification_context(
    *,
    intents: set[str],
    context: dict[str, Any],
    question: str,
    clarification_type: str,
    current_product: Product | None = None,
    reference_product: Product | None = None,
    current_order: Order | None = None,
    recent_orders: Optional[list[Order]] = None,
    addresses: Optional[list[UserAddress]] = None,
    account: User | None = None,
    ui_cards: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """统一构造“需要追问”的业务上下文，避免各分支字段不齐。"""
    return {
        "intents": sorted(intents),
        "page_context": {
            "page_type": context.get("page_type"),
            "page_path": context.get("page_path"),
            "current_product_id": current_product.id if current_product is not None else None,
            "current_order_id": current_order.id if current_order is not None else context.get("current_order_id"),
            "cart_snapshot": context.get("cart_snapshot") if isinstance(context.get("cart_snapshot"), list) else [],
        },
        "current_product": serialize_product_summary(current_product) if current_product is not None else None,
        "reference_product": serialize_product_summary(reference_product) if reference_product is not None else None,
        "candidate_products": [],
        "current_order": serialize_order_summary(current_order) if current_order is not None else None,
        "recent_orders": [serialize_order_summary(order) for order in (recent_orders or [])],
        "addresses": [serialize_address_summary(address) for address in (addresses or [])],
        "account": serialize_account_summary(account) if account is not None else None,
        "product_request": None,
        "ui_cards": ui_cards or [],
        "needs_clarification": True,
        "clarification_type": clarification_type,
        "clarification_question": question,
        "direct_answer": None,
    }


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
    status: str = "on_sale",
    exclude_product_ids: Optional[list[int]] = None,
) -> list[dict]:
    """
    搜索相似商品。

    优先使用向量相似度；若向量缺失或 Embedding 服务失败，
    自动降级到轻量文本相似，保证推荐链路可用。
    """
    stmt = (
        select(Product, ProductEmbedding)
        .outerjoin(ProductEmbedding, Product.id == ProductEmbedding.product_id)
        .options(selectinload(Product.category))
        .where(Product.status == status)
    )
    if exclude_product_ids:
        stmt = stmt.where(Product.id.not_in(exclude_product_ids))

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


async def get_product_by_id(db: AsyncSession, product_id: int) -> Product | None:
    """按 ID 查询商品详情并预加载分类。"""
    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


async def find_best_matching_product(db: AsyncSession, text: str, min_score: float = 0.45) -> Product | None:
    """
    根据用户问题里的文本，尝试匹配最可能指向的商品。

    用途：
    - 用户直接说出商品名时，可在非商品页也识别参考商品
    - 作为“类似推荐”场景中的显式锚点解析
    """
    if not (text or "").strip():
        return None

    result = await db.execute(
        select(Product)
        .options(selectinload(Product.category))
        .where(Product.status == "on_sale")
    )
    products = list(result.scalars().all())

    best_product: Product | None = None
    best_score = 0.0
    normalized_text = normalize_similarity_text(text)

    for product in products:
        product_name = normalize_similarity_text(product.name)
        score = compute_text_similarity(text, build_product_search_text(product))

        # 商品名直接命中时，给额外加权，提升显式提名的识别准确率。
        if product_name and product_name in normalized_text:
            score = max(score, 0.92)

        if score > best_score:
            best_score = score
            best_product = product

    if best_score < min_score:
        return None
    return best_product


async def get_order_by_id_for_user(db: AsyncSession, user_id: int, order_id: int) -> Order | None:
    """查询当前用户的指定订单。"""
    result = await db.execute(
        select(Order)
        .options(*order_load_options())
        .where(Order.id == order_id, Order.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def get_order_by_reference_for_user(db: AsyncSession, user_id: int, reference: str) -> Order | None:
    """根据订单号或数字 ID 查询订单。"""
    conditions = [Order.order_no == reference]
    if reference.isdigit():
        conditions.append(Order.id == int(reference))

    result = await db.execute(
        select(Order)
        .options(*order_load_options())
        .where(Order.user_id == user_id)
        .where(or_(*conditions))
    )
    return result.scalar_one_or_none()


async def get_recent_orders_for_user(db: AsyncSession, user_id: int, limit: int = 3) -> list[Order]:
    """获取用户最近订单，供 AI 做订单问答参考。"""
    result = await db.execute(
        select(Order)
        .options(*order_load_options())
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_all_orders_for_user(db: AsyncSession, user_id: int) -> list[Order]:
    """获取当前用户的全部订单。"""
    result = await db.execute(
        select(Order)
        .options(*order_load_options())
        .where(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
    )
    return list(result.scalars().all())


async def get_order_count_for_user(db: AsyncSession, user_id: int) -> int:
    """统计当前用户订单总数。"""
    result = await db.execute(
        select(func.count()).select_from(Order).where(Order.user_id == user_id)
    )
    return int(result.scalar() or 0)


async def get_addresses_for_user(db: AsyncSession, user_id: int, limit: int = 3) -> list[UserAddress]:
    """获取地址列表，默认优先默认地址。"""
    result = await db.execute(
        select(UserAddress)
        .where(UserAddress.user_id == user_id)
        .order_by(UserAddress.is_default.desc(), UserAddress.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_user_profile(db: AsyncSession, user_id: int) -> User | None:
    """查询当前用户基础资料。"""
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def deduplicate_cards(cards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按照类型 + 主键去重，避免同一轮里重复回显。"""
    deduplicated: list[dict[str, Any]] = []
    seen: set[tuple[str, Any]] = set()

    for card in cards:
        key = (str(card.get("type")), card.get("id") or card.get("order_no") or card.get("title"))
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(card)

    return deduplicated


async def build_ai_business_context(
    db: AsyncSession,
    user_id: int,
    user_message: str,
    context: dict[str, Any],
    history: list[ChatMessage],
) -> dict[str, Any]:
    """
    组装 AI 所需的业务快照。

    关键目标：
    1. 把“这件商品”“这个订单”这样的代词解析到当前页面实体
    2. 把订单/地址/账号等用户私有数据在后端查出后，以结构化数据形式交给模型
    3. 同时把需要前端回显的卡片整理出来，做到“回答”和“UI 回显”同源
    """
    intents = infer_intents(user_message, context)
    recommending_products = should_recommend_products(user_message)
    product_request = extract_product_request_constraints(user_message) if recommending_products else {
        "requested_count": None,
        "price_min": None,
        "price_max": None,
        "categories": [],
    }
    if recommending_products and is_product_follow_up_request(user_message, product_request):
        previous_product_request = extract_recent_product_request_from_history(history, user_message)
        if previous_product_request is not None:
            # 追问场景下继承上一轮预算/数量，只覆盖当前轮明确改动的条件。
            product_request = merge_product_request(product_request, previous_product_request)

    use_reference_product_for_recommendation = should_anchor_product_recommendation(
        user_message,
        context,
        product_request,
    )
    order_list_request = "order" in intents and is_order_list_request(user_message)
    current_product: Product | None = None
    reference_product: Product | None = None
    reference_product_source: str | None = None
    current_order: Order | None = None
    reference_order: Order | None = None
    recent_orders: list[Order] = []
    order_count = 0
    addresses: list[UserAddress] = []
    reference_address: UserAddress | None = None
    account: User | None = None
    ui_cards: list[dict[str, Any]] = []
    candidate_products: list[dict[str, Any]] = []

    if needs_generic_clarification(intents, user_message):
        return build_clarification_context(
            intents=intents,
            context=context,
            question=build_generic_clarification(),
            clarification_type="generic_target",
        )

    if is_purchase_history_request(user_message):
        all_orders = await get_all_orders_for_user(db, user_id)
        history_cards, summary = build_purchase_history_snapshot(all_orders)
        if not all_orders:
            summary = "你目前还没有历史下单记录。"

        return {
            "intents": sorted(intents | {"order", "product"}),
            "page_context": {
                "page_type": context.get("page_type"),
                "page_path": context.get("page_path"),
                "current_product_id": context.get("current_product_id"),
                "current_order_id": context.get("current_order_id"),
                "cart_snapshot": context.get("cart_snapshot") if isinstance(context.get("cart_snapshot"), list) else [],
            },
            "current_product": None,
            "reference_product": None,
            "candidate_products": [],
            "current_order": None,
            "recent_orders": [serialize_order_summary(order) for order in all_orders[:5]],
            "addresses": [],
            "account": None,
            "product_request": None,
            "order_count": len(all_orders),
            "order_list_request": False,
            "purchase_history_request": True,
            "ui_cards": history_cards,
            "needs_clarification": False,
            "clarification_type": None,
            "clarification_question": None,
            "direct_answer": summary,
        }

    current_product_id = context.get("current_product_id")
    if isinstance(current_product_id, int):
        current_product = await get_product_by_id(db, current_product_id)
        if current_product is not None and (not recommending_products or use_reference_product_for_recommendation):
            reference_product = current_product
            reference_product_source = "current_page"

    current_order_id = context.get("current_order_id")
    if isinstance(current_order_id, int):
        current_order = await get_order_by_id_for_user(db, user_id, current_order_id)
        reference_order = current_order

    if reference_product is None and "product" in intents and (not recommending_products or use_reference_product_for_recommendation):
        reference_product = await find_best_matching_product(db, user_message)
        if reference_product is not None:
            reference_product_source = "message_match"

    if reference_product is None and "product" in intents and (not recommending_products or use_reference_product_for_recommendation):
        latest_product_card = extract_latest_typed_card_from_history(history, "product")
        latest_product_id = latest_product_card.get("id") if isinstance(latest_product_card, dict) else None
        if isinstance(latest_product_id, int):
            reference_product = await get_product_by_id(db, latest_product_id)
            if reference_product is not None:
                reference_product_source = "history_product"

    if reference_product is not None and "product" in intents and not recommending_products:
        reason = "当前页面商品"
        if reference_product_source == "message_match":
            reason = "根据你这次提到的商品匹配"
        elif reference_product_source == "history_product":
            reason = "沿用你刚刚咨询过的商品"

        ui_cards.append(
            serialize_product_card(
                reference_product,
                reason=reason,
                source="context",
            )
        )

    if "product" in intents:
        search_query = user_message
        exclude_ids: list[int] = []

        # 无法判断“类似推荐”依据时，先追问用户，不直接让模型胡猜。
        if recommending_products and reference_product is None and is_generic_similar_product_request(user_message):
            return build_clarification_context(
                intents=intents,
                context=context,
                question=build_product_reference_clarification(),
                clarification_type="product_reference",
                current_product=current_product,
                current_order=current_order,
                ui_cards=[],
            )

        # 当前商品页 / 明确提名 / 最近上下文下，推荐类问法优先以“参考商品文本 + 用户意图”检索相似款。
        if reference_product is not None and (not recommending_products or use_reference_product_for_recommendation):
            exclude_ids.append(reference_product.id)
            if recommending_products or has_any_keyword(user_message, PRODUCT_REFERENCE_KEYWORDS):
                search_query = " ".join(
                    part for part in [
                        reference_product.name,
                        reference_product.description or "",
                        user_message,
                    ]
                    if part
                )

        try:
            similar_products = await search_similar_products(
                db,
                query=search_query,
                top_k=max((product_request.get("requested_count") or 4) * 4, 8),
                exclude_product_ids=exclude_ids or None,
            )
        except Exception:
            logger.exception("商品推荐检索失败，已降级为无推荐模式")
            similar_products = []

        if recommending_products:
            similar_products = filter_similar_products_by_constraints(similar_products, product_request)

        candidate_products = [
            {
                **serialize_product_summary(item["product"]),
                "similarity": round(float(item["similarity"]), 4),
                "source": item["source"],
            }
            for item in similar_products
        ]

        if recommending_products and not candidate_products and has_product_constraints(product_request):
            return {
                "intents": sorted(intents),
                "page_context": {
                    "page_type": context.get("page_type"),
                    "page_path": context.get("page_path"),
                    "current_product_id": current_product.id if current_product is not None else None,
                    "current_order_id": current_order.id if current_order is not None else current_order_id,
                    "cart_snapshot": context.get("cart_snapshot") if isinstance(context.get("cart_snapshot"), list) else [],
                },
                "current_product": serialize_product_summary(current_product) if current_product is not None else None,
                "reference_product": serialize_product_summary(reference_product) if reference_product is not None else None,
                "candidate_products": [],
                "current_order": serialize_order_summary(reference_order or current_order) if (reference_order or current_order) is not None else None,
                "recent_orders": [serialize_order_summary(order) for order in recent_orders],
                "addresses": [serialize_address_summary(address) for address in addresses],
                "account": serialize_account_summary(account) if account is not None else None,
                "product_request": product_request,
                # 这里直接返回文本说明，不再额外附带重复的 info 卡片，
                # 避免前端出现“同一句没结果提示既输出文字又输出卡片”的重复展示。
                "ui_cards": [],
                "needs_clarification": False,
                "clarification_type": None,
                "clarification_question": None,
                "direct_answer": build_no_matching_products_answer(product_request),
            }

        if recommending_products:
            for item in similar_products:
                ui_cards.append(
                    serialize_product_card(
                        item["product"],
                        similarity=item["similarity"],
                        reason="根据当前问题推荐的相似商品",
                        source=item["source"],
                    )
                )

    if "order" in intents:
        order_reference = extract_order_reference(user_message)
        if reference_order is None and order_reference:
            reference_order = await get_order_by_reference_for_user(db, user_id, order_reference)

        if reference_order is None and not order_list_request:
            latest_order_card = extract_latest_typed_card_from_history(history, "order")
            latest_order_id = latest_order_card.get("id") if isinstance(latest_order_card, dict) else None
            if isinstance(latest_order_id, int):
                reference_order = await get_order_by_id_for_user(db, user_id, latest_order_id)

        if reference_order is None:
            recent_orders = await get_recent_orders_for_user(db, user_id, limit=5 if order_list_request else 3)
            if len(recent_orders) == 1 and is_singular_order_request(user_message):
                reference_order = recent_orders[0]

        if order_list_request and reference_order is None and intents == {"order"}:
            order_count = await get_order_count_for_user(db, user_id)
            preview_cards = [serialize_order_card(order, reason="最近订单") for order in recent_orders[:5]]
            return {
                "intents": sorted(intents),
                "page_context": {
                    "page_type": context.get("page_type"),
                    "page_path": context.get("page_path"),
                    "current_product_id": current_product.id if current_product is not None else None,
                    "current_order_id": current_order.id if current_order is not None else current_order_id,
                    "cart_snapshot": context.get("cart_snapshot") if isinstance(context.get("cart_snapshot"), list) else [],
                },
                "current_product": serialize_product_summary(current_product) if current_product is not None else None,
                "reference_product": serialize_product_summary(reference_product) if reference_product is not None else None,
                "candidate_products": candidate_products,
                "current_order": serialize_order_summary(reference_order or current_order) if (reference_order or current_order) is not None else None,
                "recent_orders": [serialize_order_summary(order) for order in recent_orders],
                "addresses": [serialize_address_summary(address) for address in addresses],
                "account": serialize_account_summary(account) if account is not None else None,
                "product_request": product_request if recommending_products else None,
                "order_count": order_count,
                "order_list_request": True,
                "ui_cards": preview_cards,
                "needs_clarification": False,
                "clarification_type": None,
                "clarification_question": None,
                "direct_answer": build_order_list_answer(order_count, len(preview_cards)),
            }

        if reference_order is None and is_singular_order_request(user_message):
            if not recent_orders:
                recent_orders = await get_recent_orders_for_user(db, user_id, limit=3)
            preview_cards = [serialize_order_card(order, reason="最近订单") for order in recent_orders[:2]]
            return build_clarification_context(
                intents=intents,
                context=context,
                question=build_order_reference_clarification(),
                clarification_type="order_reference",
                current_product=current_product,
                reference_product=reference_product,
                current_order=current_order,
                recent_orders=recent_orders,
                ui_cards=preview_cards,
            )

        if reference_order is not None:
            ui_cards.append(serialize_order_card(reference_order, reason="与当前问题最相关的订单"))
        else:
            if not recent_orders:
                recent_orders = await get_recent_orders_for_user(db, user_id, limit=3)
            for order in recent_orders[:5]:
                ui_cards.append(serialize_order_card(order, reason="最近订单"))

    if "address" in intents:
        addresses = await get_addresses_for_user(db, user_id, limit=3)
        if addresses:
            if is_default_address_request(user_message):
                reference_address = next((address for address in addresses if address.is_default == 1), addresses[0])
            elif is_singular_address_request(user_message):
                latest_address_card = extract_latest_typed_card_from_history(history, "address")
                latest_address_id = latest_address_card.get("id") if isinstance(latest_address_card, dict) else None
                if isinstance(latest_address_id, int):
                    reference_address = next((address for address in addresses if address.id == latest_address_id), None)

                if reference_address is None and len(addresses) == 1:
                    reference_address = addresses[0]

                if reference_address is None:
                    preview_cards = [
                        serialize_address_card(
                            address,
                            reason="默认收货地址" if address.is_default == 1 else f"常用地址 {index + 1}",
                        )
                        for index, address in enumerate(addresses[:2])
                    ]
                    return build_clarification_context(
                        intents=intents,
                        context=context,
                        question=build_address_reference_clarification(),
                        clarification_type="address_reference",
                        current_product=current_product,
                        reference_product=reference_product,
                        current_order=reference_order or current_order,
                        recent_orders=recent_orders,
                        addresses=addresses,
                        ui_cards=preview_cards,
                    )

            if reference_address is not None:
                ui_cards.append(
                    serialize_address_card(
                        reference_address,
                        reason="默认收货地址" if reference_address.is_default == 1 else "与你当前问题最相关的地址",
                    )
                )
            else:
                for index, address in enumerate(addresses[:2]):
                    reason = "默认收货地址" if address.is_default == 1 else f"常用地址 {index + 1}"
                    ui_cards.append(serialize_address_card(address, reason=reason))
        else:
            ui_cards.append(
                serialize_context_card(
                    {
                        "title": "暂无收货地址",
                        "description": "系统里还没有查到你的收货地址，可以先去地址管理页新增。",
                    }
                )
            )

    if "account" in intents:
        account = await get_user_profile(db, user_id)
        if account is not None:
            ui_cards.append(serialize_account_card(account, reason="当前账号资料"))

    ui_cards = deduplicate_cards(ui_cards)

    page_context = {
        "page_type": context.get("page_type"),
        "page_path": context.get("page_path"),
        "current_product_id": current_product.id if current_product is not None else None,
        "current_order_id": current_order.id if current_order is not None else current_order_id,
        "cart_snapshot": context.get("cart_snapshot") if isinstance(context.get("cart_snapshot"), list) else [],
    }

    return {
        "intents": sorted(intents),
        "page_context": page_context,
        "current_product": serialize_product_summary(current_product) if current_product is not None else None,
        "reference_product": serialize_product_summary(reference_product) if reference_product is not None else None,
        "candidate_products": candidate_products,
        "current_order": serialize_order_summary(reference_order or current_order) if (reference_order or current_order) is not None else None,
        "recent_orders": [serialize_order_summary(order) for order in recent_orders],
        "addresses": [serialize_address_summary(address) for address in addresses],
        "account": serialize_account_summary(account) if account is not None else None,
        "product_request": product_request if recommending_products else None,
        "order_count": order_count if order_list_request else None,
        "order_list_request": order_list_request,
        "ui_cards": ui_cards,
        "needs_clarification": False,
        "clarification_type": None,
        "clarification_question": None,
        "direct_answer": None,
    }


def build_ai_system_prompt() -> str:
    """系统提示词：明确 AI 的边界与输出风格。"""
    return (
        "你是一位专业的电商导购与订单助手，名叫「智购小助手」。"
        "你要同时处理商品咨询、相似商品推荐、订单进度、地址信息、账号资料等问题。"
        "请严格遵守下面规则："
        "1. 只基于系统提供的业务快照回答用户的私有信息，不要编造订单、地址、账号数据。"
        "2. 如果用户说“这件商品”“这个订单”等指代词，优先使用 page_context/current_product/current_order 里的实体。"
        "3. 商品推荐优先结合 current_product、candidate_products 与 product_request，回答要自然、像导购，不要机械罗列 JSON。"
        "4. 如果用户问的是订单列表、全部订单或最近订单，不要只返回单笔订单，要按列表问题处理；当 business_context.order_list_request 为 true 时，优先把 recent_orders 作为列表预览，并结合 order_count 说明总数。"
        "5. 页面上下文只是辅助消歧，不要覆盖用户已经明确表达的业务意图。"
        "6. 当系统没有查到数据时，要明确说明未查到，并给出下一步建议。"
        "7. 不要泄露密码、Token、数据库、内部实现等敏感信息。"
        "8. 如果用户明确给了品类、预算或数量，只能从 candidate_products 中推荐，数量不能超过 product_request.requested_count；若 candidate_products 为空，就明确说明没找到，不要推荐其他品类商品。"
        "9. 回答尽量简洁友好，适度使用分点，但不要过度冗长。"
    )


async def chat_with_ai(
    db: AsyncSession,
    user_id: int,
    user_message: str,
    context: Optional[dict] = None
) -> dict:
    """
    与 AI 对话的准备步骤。

    本轮会做两类工作：
    - 聊天链路：保存用户消息、读取最近历史
    - 业务链路：根据当前页面上下文和关键词召回商品/订单/地址/账号数据
    """
    normalized_context = context or {}
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
        .limit(12)
    )
    history = history_result.scalars().all()
    history.reverse()

    business_context = await build_ai_business_context(
        db=db,
        user_id=user_id,
        user_message=user_message,
        context=normalized_context,
        history=history,
    )

    if business_context.get("needs_clarification"):
        return {
            "messages": [],
            "ui_cards": business_context["ui_cards"],
            "business_context": business_context,
            "direct_answer": business_context.get("clarification_question") or "请你再补充一点信息，我才能继续帮你判断。",
        }

    if isinstance(business_context.get("direct_answer"), str) and business_context["direct_answer"].strip():
        return {
            "messages": [],
            "ui_cards": business_context["ui_cards"],
            "business_context": business_context,
            "direct_answer": business_context["direct_answer"],
        }

    messages = [
        {
            "role": "system",
            "content": build_ai_system_prompt(),
        },
        {
            # AI 路由与业务计算分离：这里把后端查出的结构化业务快照统一喂给模型，
            # 前端只负责传当前页面上下文，模型不直接碰数据库。
            "role": "system",
            "content": (
                "以下是本轮对话可用的业务快照 JSON，请仅基于这些数据回答：\n"
                f"{json.dumps(business_context, ensure_ascii=False)}"
            ),
        },
    ]

    for msg in history[-6:]:
        messages.append({
            "role": msg.role,
            "content": msg.content
        })

    return {
        "messages": messages,
        "ui_cards": business_context["ui_cards"],
        "business_context": business_context,
    }


async def generate_streaming_response(messages: list[dict]):
    """
    生成流式响应（SSE）。
    对前端统一输出 `type=delta` 事件，便于打字机效果与结构化事件并存。
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
            yield f"data: {json.dumps({'type': 'delta', 'content': content}, ensure_ascii=False)}\n\n"

    yield "data: [DONE]\n\n"
