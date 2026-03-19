"""
AI 对话相关 Pydantic Schemas
"""
from pydantic import BaseModel
from typing import Optional


class ChatMessageCreate(BaseModel):
    """用户发送消息请求"""
    content: str
    context: Optional[dict] = None  # 前端上下文 (如当前页面、购物车状态等)


class ChatMessageResponse(BaseModel):
    """对话消息响应"""
    id: int
    user_id: int
    role: str
    content: str
    ui_type: Optional[str] = None
    payload: Optional[str] = None
    created_at: str
    
    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    """对话历史响应"""
    total: int
    messages: list[ChatMessageResponse]
