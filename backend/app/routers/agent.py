from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.limiter import limiter
from app.models.merchant import Merchant
from app.schemas.agent import ChatRequest, ChatResponse
from app.security import get_current_merchant
from app.services import agent

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
def chat_with_agent(
    req: Request,
    request: ChatRequest,
    current: Merchant = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    reply, tool_calls = agent.handle_chat(db, current.id, request.messages)
    return ChatResponse(reply=reply, tool_calls=tool_calls)
