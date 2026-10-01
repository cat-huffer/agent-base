from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.schemas.chat import ChatRequest, ChatResponse, ChatStreamEvent
from app.services.chat import ChatService

router = APIRouter()
chat_service = ChatService()

# 非流式输出
@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    result = await chat_service.chat(request.session_id, request.message)
    return ChatResponse(message=result.message, trace_id=result.trace_id)


def _sse(event: ChatStreamEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json(exclude_none=True)}\n\n"

# 流式输出
@router.post("/chat/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    async def events() -> AsyncIterator[str]:
        async with aclosing(chat_service.stream(request.session_id, request.message)) as stream:
            async for event in stream:
                yield _sse(ChatStreamEvent(**event.__dict__))

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
