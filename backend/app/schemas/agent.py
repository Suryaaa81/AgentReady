from typing import Any

from pydantic import BaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    merchant_id: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    reply: str
    tool_calls: list[dict[str, Any]] = []
