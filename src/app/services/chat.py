import asyncio
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass, field
from pathlib import Path

from agents import RunConfig, Runner, gen_trace_id
from agents.extensions.memory import AsyncSQLiteSession
from loguru import logger
from openai.types.responses import ResponseTextDeltaEvent

from agent.agents.router import assemble_router_agent
from agent.models.router import ModelRouter, model_router
from agent.prompts.render import PromptRender
from app.config import settings
from app.services.events import ChatStreamEvent


@dataclass(frozen=True)
class ChatResult:
    message: str
    trace_id: str


@dataclass
class _SessionGate:
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    users: int = 0


@dataclass(frozen=True)
class _ChatExecution:
    session: AsyncSQLiteSession
    run_config: RunConfig


class ChatService:
    def __init__(
        self,
        session_db_path: Path | None = None,
        *,
        router: ModelRouter | None = None,
        prompt_renderer: PromptRender | None = None,
    ) -> None:
        router = router if router is not None else model_router
        prompt_renderer = prompt_renderer if prompt_renderer is not None else PromptRender()
        assembly = assemble_router_agent(router=router, prompt_renderer=prompt_renderer)
        self.agent = assembly.agent
        self.model_profile = assembly.model_profile
        self.prompt_profile = assembly.prompt_profile
        self.session_db_path = (
            session_db_path if session_db_path is not None else settings.session_db_path
        )
        self._session_gates: dict[str, _SessionGate] = {}
        self._session_gates_lock = asyncio.Lock()

    def _run_config(self, session_id: str, trace_id: str) -> RunConfig:
        tracing_key = settings.openai_tracing_api_key
        return RunConfig(
            workflow_name="chat",
            trace_id=trace_id,
            group_id=session_id,
            trace_metadata={
                "session_id": session_id,
                "agent": self.agent.name.lower(),
                "model_profile": self.model_profile.name,
                "prompt": self.prompt_profile.id,
                "prompt_version": self.prompt_profile.version,
                "environment": settings.app_env,
            },
            tracing_disabled=not bool(tracing_key),
            tracing={"api_key": tracing_key} if tracing_key else None,
            trace_include_sensitive_data=False,
        )

    @asynccontextmanager
    async def _execution(self, session_id: str, trace_id: str) -> AsyncIterator[_ChatExecution]:
        async with self._session_gates_lock:
            gate = self._session_gates.setdefault(session_id, _SessionGate())
            gate.users += 1
        try:
            async with gate.lock:
                self.session_db_path.parent.mkdir(parents=True, exist_ok=True)
                session = AsyncSQLiteSession(session_id, db_path=self.session_db_path)
                try:
                    yield _ChatExecution(
                        session=session, run_config=self._run_config(session_id, trace_id)
                    )
                finally:
                    await session.close()
        finally:
            async with self._session_gates_lock:
                gate.users -= 1
                if gate.users == 0:
                    del self._session_gates[session_id]

    async def chat(self, session_id: str, message: str) -> ChatResult:
        trace_id = gen_trace_id()
        try:
            async with self._execution(session_id, trace_id) as execution:
                result = await Runner.run(
                    starting_agent=self.agent,
                    input=message,
                    session=execution.session,
                    run_config=execution.run_config,
                )
            if not isinstance(result.final_output, str):
                raise RuntimeError("router did not return a text response")
            return ChatResult(message=result.final_output, trace_id=trace_id)
        except Exception:
            logger.exception("chat failed: trace_id={}", trace_id)
            raise

    async def stream(self, session_id: str, message: str) -> AsyncGenerator[ChatStreamEvent, None]:
        trace_id = gen_trace_id()
        yield ChatStreamEvent(type="started", trace_id=trace_id)
        try:
            async with self._execution(session_id, trace_id) as execution:
                result = Runner.run_streamed(
                    starting_agent=self.agent,
                    input=message,
                    session=execution.session,
                    run_config=execution.run_config,
                )
                events = result.stream_events()
                try:
                    async for event in events:
                        if event.type == "raw_response_event" and isinstance(
                            event.data, ResponseTextDeltaEvent
                        ):
                            yield ChatStreamEvent(
                                type="message.delta", trace_id=trace_id, delta=event.data.delta
                            )
                finally:
                    interrupted = not result.is_complete
                    if interrupted:
                        result.cancel()
                    if isinstance(events, AsyncGenerator):
                        with suppress(Exception):
                            await events.aclose()
                    if interrupted:
                        with suppress(Exception):
                            async for _ in result.stream_events():
                                pass
                if not isinstance(result.final_output, str):
                    raise RuntimeError("router did not return a text response")
                final_message = result.final_output
            yield ChatStreamEvent(type="completed", trace_id=trace_id, message=final_message)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("chat stream failed: trace_id={}", trace_id)
            yield ChatStreamEvent(type="error", trace_id=trace_id, message="Chat failed")
