from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1)
    message: str


class ChatResponse(BaseModel):
    message: str
    trace_id: str


class ChatStreamEvent(BaseModel):
    type: Literal["started", "message.delta", "completed", "error"]
    trace_id: str
    delta: str | None = None
    message: str | None = None
