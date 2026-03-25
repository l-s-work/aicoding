"""
AI 对话路由：智能推荐、流式对话
"""
import json
from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.api.deps import DatabaseSession, CurrentUser, CurrentAdmin
from app.db.models import ChatMessage
from app.schemas.chat_schema import ChatMessageCreate, ChatMessageResponse, ChatHistoryResponse
from app.services.ai_service import chat_with_ai, generate_streaming_response, sync_product_embedding

router = APIRouter(prefix="/ai", tags=["AI 智能助手"])


@router.post("/chat/stream")
async def chat_stream(
    message_data: ChatMessageCreate,
    db: DatabaseSession,
    current_user: CurrentUser
):
    """
    AI 对话流式接口 (SSE)

    - 前端通过 fetch + SSE 读取打字机流
    - 同一条回复中可同时返回文本和结构化卡片
    """
    chat_data = await chat_with_ai(
        db=db,
        user_id=current_user.id,
        user_message=message_data.content,
        context=message_data.context
    )

    messages = chat_data["messages"]
    ui_cards = chat_data["ui_cards"]
    direct_answer = chat_data.get("direct_answer")

    async def event_generator():
        if isinstance(direct_answer, str) and direct_answer.strip():
            yield f"data: {json.dumps({'type': 'delta', 'content': direct_answer}, ensure_ascii=False)}\n\n"
            if ui_cards:
                yield f"data: {json.dumps({'type': 'cards', 'cards': ui_cards}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

            assistant_msg = ChatMessage(
                user_id=current_user.id,
                role="assistant",
                content=direct_answer,
                ui_type="text" if not ui_cards else "structured_cards",
                payload=json.dumps(ui_cards, ensure_ascii=False) if ui_cards else None,
                created_at=datetime.utcnow().isoformat()
            )
            db.add(assistant_msg)
            await db.commit()
            return

        full_response = ""
        async for chunk in generate_streaming_response(messages):
            if chunk == "data: [DONE]\n\n":
                continue

            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                try:
                    data = json.loads(chunk[6:])
                    content = data.get("content", "") if isinstance(data, dict) else ""
                    if content:
                        full_response += content
                except json.JSONDecodeError:
                    pass

            yield chunk

        if ui_cards:
            # 结构化卡片按接口输出顺序紧跟在文本之后返回，
            # 由前端直接按事件顺序展示，避免“卡片先到、文字后补”的错位体验。
            yield f"data: {json.dumps({'type': 'cards', 'cards': ui_cards}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

        assistant_msg = ChatMessage(
            user_id=current_user.id,
            role="assistant",
            content=full_response,
            ui_type="text" if not ui_cards else "structured_cards",
            payload=json.dumps(ui_cards, ensure_ascii=False) if ui_cards else None,
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

    chat_data = await chat_with_ai(
        db=db,
        user_id=current_user.id,
        user_message=message_data.content,
        context=message_data.context
    )

    messages = chat_data["messages"]
    ui_cards = chat_data["ui_cards"]
    direct_answer = chat_data.get("direct_answer")

    if isinstance(direct_answer, str) and direct_answer.strip():
        assistant_msg = ChatMessage(
            user_id=current_user.id,
            role="assistant",
            content=direct_answer,
            ui_type="text" if not ui_cards else "structured_cards",
            payload=json.dumps(ui_cards, ensure_ascii=False) if ui_cards else None,
            created_at=datetime.utcnow().isoformat()
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)
        return assistant_msg

    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=messages,
        temperature=0.7,
    )

    assistant_content = response.choices[0].message.content or ""

    assistant_msg = ChatMessage(
        user_id=current_user.id,
        role="assistant",
        content=assistant_content,
        ui_type="text" if not ui_cards else "structured_cards",
        payload=json.dumps(ui_cards, ensure_ascii=False) if ui_cards else None,
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
    messages.reverse()

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
    admin: CurrentAdmin = None
):
    """
    同步商品 Embedding (管理员或开发测试用)

    - force=True 强制重新生成
    """
    # 该接口会触发额外计算与外部调用，收敛到管理员权限，避免普通用户滥用。
    await sync_product_embedding(db, product_id, force=force)
