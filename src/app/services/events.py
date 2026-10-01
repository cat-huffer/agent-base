from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ChatStreamEvent:
    type: Literal["started", "message.delta", "completed", "error"]
    trace_id: str
    delta: str | None = None
    message: str | None = None
