"""
AI 对话路由：智能推荐、流式对话
"""
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DatabaseSession, CurrentUser
from app.db.models import ChatMessage, Product
from app.schemas.chat_schema import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from app.services.ai_service import (
    chat_with_ai, generate_streaming_response,
    search_similar_products, sync_product_embedding
)

router = APIRouter(prefix="/ai", tags=["AI 智能助手"])


@router.post("/chat/stream")
async def chat_stream(
    message_data: ChatMessageCreate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """
    AI 对话流式接口 (SSE)
    
    - 前端通过 EventSource 连接
    - 实时打字机效果
    - 返回推荐商品卡片
    """
    # 准备对话数据
    chat_data = await chat_with_ai(
        db=db,
        user_id=current_user.id,
        user_message=message_data.content,
        context=message_data.context
    )
    
    messages = chat_data["messages"]
    similar_products = chat_data["similar_products"]
    
    # 定义 SSE 生成器
    async def event_generator():
        # 1. 先发送推荐商品卡片
        if similar_products:
            products_json = [
                {
                    "id": item["product"].id,
                    "name": item["product"].name,
                    "price": item["product"].price,
                    "image_url": item["product"].image_url,
                    "similarity": item["similarity"]
                }
                for item in similar_products
            ]
            
            yield f"data: {json.dumps({'type': 'products', 'products': products_json}, ensure_ascii=False)}\n\n"
        
        # 2. 流式输出 AI 回复
        full_response = ""
        async for chunk in generate_streaming_response(messages):
            # 解析内容
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:])
                    content = data.get("content", "")
                    if content:
                        full_response += content
                except:
                    pass
            
            yield chunk
        
        # 3. 保存 AI 回复到数据库
        assistant_msg = ChatMessage(
            user_id=current_user.id,
            role="assistant",
            content=full_response,
            ui_type="text" if not similar_products else "product_cards",
            payload=json.dumps(products_json, ensure_ascii=False) if similar_products else None,
            created_at=datetime.utcnow().isoformat()
        )
        db.add(assistant_msg)
        await db.commit()
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/chat", response_model=ChatMessageResponse)
async def chat_non_stream(
    message_data: ChatMessageCreate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """
    AI 对话非流式接口 (传统 JSON 响应)
    
    - 用于不支持 SSE 的场景
    """
    from openai import AsyncOpenAI
    from app.core.config import settings
    
    client = AsyncOpenAI(
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL
    )
    
    # 准备对话
    chat_data = await chat_with_ai(
        db=db,
        user_id=current_user.id,
        user_message=message_data.content,
        context=message_data.context
    )
    
    messages = chat_data["messages"]
    similar_products = chat_data["similar_products"]
    
    # 调用 OpenAI（非流式）
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )
    
    assistant_content = response.choices[0].message.content
    
    # 保存回复
    products_json = None
    if similar_products:
        products_json = [
            {
                "id": item["product"].id,
                "name": item["product"].name,
                "price": item["product"].price,
                "image_url": item["product"].image_url,
            }
            for item in similar_products
        ]
    
    assistant_msg = ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content=assistant_content,
        ui_type="text" if not similar_products else "product_cards",
        payload=json.dumps(products_json, ensure_ascii=False) if products_json else None,
        created_at=datetime.utcnow().isoformat()
    )
    db.add(assistant_msg)
    await db.commit()
    await db.refresh(assistant_msg)
    
    return assistant_msg


@router.get("/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    limit: int = 50,
    db: DatabaseSession = None,
    current_user: CurrentUser = None
):
    """获取对话历史"""
    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.user_id == current_user.id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
    )
    messages = result.scalars().all()
    messages.reverse()  # 时间正序
    
    return ChatHistoryResponse(
        total=len(messages),
        messages=messages
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_chat_history(db: DatabaseSession, current_user: CurrentUser):
    """清空对话历史"""
    result = await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == current_user.id)
    )
    messages = result.scalars().all()
    
    for msg in messages:
        await db.delete(msg)
    
    await db.commit()


@router.post("/products/{product_id}/sync-embedding", status_code=status.HTTP_204_NO_CONTENT)
async def sync_embedding(
    product_id: int,
    force: bool = False,
    db: DatabaseSession = None,
    current_user: CurrentUser = None
):
    """
    同步商品 Embedding (管理员或开发测试用)
    
    - force=True 强制重新生成
    """
    await sync_product_embedding(db, product_id, force=force)
