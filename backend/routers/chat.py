"""/api/chat — assistant endpoint with platform context injection."""
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services import llm_service, market_data, news_aggregator

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Register the platform's context providers once at import time. Additional
# sources (documents, knowledge repo) just call register_context_provider.
llm_service.register_context_provider(lambda _msg: market_data.market_snapshot_text())
llm_service.register_context_provider(lambda _msg: news_aggregator.recent_headlines_text())


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=64)
    message: str = Field(min_length=1, max_length=4000)


@router.post("")
def chat(req: ChatRequest):
    return llm_service.chat(req.session_id, req.message)


@router.get("/history/{session_id}")
def history(session_id: str):
    return {"messages": llm_service.get_history(session_id)}


@router.delete("/history/{session_id}")
def clear(session_id: str):
    llm_service.clear_history(session_id)
    return {"cleared": True}


@router.get("/status")
def status():
    backend = llm_service.get_backend()
    return {"backend": backend.name, "available": llm_service.llm_available()}
