import asyncio
from types import SimpleNamespace

from agents import Agent
from agents.extensions.memory import AsyncSQLiteSession
from fastapi.testclient import TestClient
from openai.types.responses import ResponseTextDeltaEvent

from app.config import settings
from app.main import app
from app.schemas.chat import ChatStreamEvent
from app.services.chat import ChatService


def test_chat_service_runs_router_with_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    received = {}

    async def fake_run(*, starting_agent, input, session, run_config):
        received["agent"] = starting_agent
        received["input"] = input
        received["session_id"] = session.session_id
        received["session_type"] = type(session)
        received["run_config"] = run_config
        return SimpleNamespace(final_output="Hello from router")

    monkeypatch.setattr("app.services.chat.Runner.run", fake_run)

    result = asyncio.run(ChatService(tmp_path / "sessions.db").chat("abc123", "Hello"))

    assert result.message == "Hello from router"
    assert result.trace_id.startswith("trace_")
    assert received["input"] == "Hello"
    assert received["session_id"] == "abc123"
    assert received["session_type"] is AsyncSQLiteSession
    assert isinstance(received["agent"], Agent)
    assert received["agent"].name == "Router"
    assert received["agent"].model == "deepseek-flash"
    assert "入口路由 Agent" in received["agent"].instructions
    assert received["run_config"].trace_id == result.trace_id
    assert received["run_config"].group_id == "abc123"
    assert received["run_config"].trace_metadata == {
        "session_id": "abc123",
        "agent": "router",
        "model_profile": "fast",
        "prompt": "router",
        "prompt_version": "1.0.0",
        "environment": "development",
    }
    assert received["run_config"].tracing_disabled is True
    assert received["run_config"].trace_include_sensitive_data is False


def test_chat_service_enables_sdk_export_with_separate_tracing_key(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", "test-tracing-key")
    received = {}

    async def fake_run(*, starting_agent, input, session, run_config):
        received["run_config"] = run_config
        return SimpleNamespace(final_output="reply")

    monkeypatch.setattr("app.services.chat.Runner.run", fake_run)
    result = asyncio.run(ChatService(tmp_path / "sessions.db").chat("abc123", "Hello"))

    assert result.message == "reply"
    assert received["run_config"].tracing_disabled is False
    assert received["run_config"].tracing["api_key"] == "test-tracing-key"


def test_chat_service_reuses_history_across_requests(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    histories = []
    trace_ids = []

    async def fake_run(*, starting_agent, input, session, run_config):
        histories.append((session.session_id, await session.get_items()))
        trace_ids.append(run_config.trace_id)
        await session.add_items([{"role": "user", "content": input}])
        return SimpleNamespace(final_output="reply")

    monkeypatch.setattr("app.services.chat.Runner.run", fake_run)
    service = ChatService(tmp_path / "sessions.db")

    asyncio.run(service.chat("abc123", "我叫张三"))
    asyncio.run(service.chat("abc123", "我叫什么？"))
    asyncio.run(service.chat("another", "我叫什么？"))

    assert histories == [
        ("abc123", []),
        ("abc123", [{"role": "user", "content": "我叫张三"}]),
        ("another", []),
    ]
    assert len(set(trace_ids)) == 3


def test_chat_endpoint_returns_json_response(monkeypatch) -> None:
    async def fake_chat(session_id: str, message: str):
        assert session_id == "abc123"
        assert message == "Hello"
        return SimpleNamespace(message="Hello from assistant", trace_id="trace_test123")

    monkeypatch.setattr("app.api.chat.chat_service.chat", fake_chat)

    with TestClient(app) as client:
        response = client.post("/chat", json={"session_id": "abc123", "message": "Hello"})
        health = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"message": "Hello from assistant", "trace_id": "trace_test123"}
    assert health.json() == {"status": "ok"}


def test_chat_endpoint_requires_session_id_and_message() -> None:
    with TestClient(app) as client:
        missing_id = client.post("/chat", json={"message": "Hello"})
        missing_message = client.post("/chat", json={"session_id": "abc123"})

    assert missing_id.status_code == 422
    assert missing_message.status_code == 422


def test_chat_service_streams_text_and_final_output(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    received = {}

    class FakeStream:
        final_output = "Hello!"
        is_complete = False

        async def stream_events(self):
            yield SimpleNamespace(
                type="raw_response_event",
                data=ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    content_index=0,
                    delta="Hello",
                    item_id="item_1",
                    logprobs=[],
                    output_index=0,
                    sequence_number=1,
                ),
            )
            yield SimpleNamespace(type="agent_updated_stream_event")
            self.is_complete = True

        def cancel(self):
            raise AssertionError("completed stream must not be cancelled")

    def fake_run_streamed(*, starting_agent, input, session, run_config):
        received["session"] = session
        received["run_config"] = run_config
        return FakeStream()

    monkeypatch.setattr("app.services.chat.Runner.run_streamed", fake_run_streamed)

    async def collect():
        return [event async for event in ChatService(tmp_path / "sessions.db").stream("abc", "Hi")]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["started", "message.delta", "completed"]
    assert events[1].delta == "Hello"
    assert events[2].message == "Hello!"
    assert events[0].trace_id == events[1].trace_id == events[2].trace_id
    assert received["run_config"].trace_id == events[0].trace_id
    assert isinstance(received["session"], AsyncSQLiteSession)


def test_chat_stream_endpoint_returns_sse(monkeypatch) -> None:
    async def fake_stream(session_id: str, message: str):
        assert (session_id, message) == ("abc", "Hi")
        yield ChatStreamEvent(type="started", trace_id="trace_test")
        yield ChatStreamEvent(type="message.delta", trace_id="trace_test", delta="Hello")
        yield ChatStreamEvent(type="completed", trace_id="trace_test", message="Hello")

    monkeypatch.setattr("app.api.chat.chat_service.stream", fake_stream)

    with TestClient(app) as client:
        response = client.post("/chat/stream", json={"session_id": "abc", "message": "Hi"})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: started\ndata: " in response.text
    assert '"type":"message.delta","trace_id":"trace_test","delta":"Hello"' in response.text
    assert "event: completed\ndata: " in response.text


def test_chat_service_serializes_same_session_across_stream_and_chat(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    stream_started = asyncio.Event()
    release_stream = asyncio.Event()
    chat_started = asyncio.Event()

    class FakeStream:
        final_output = "first reply"
        is_complete = False

        async def stream_events(self):
            stream_started.set()
            await release_stream.wait()
            self.is_complete = True
            if False:
                yield None

        def cancel(self):
            self.is_complete = True

    def fake_run_streamed(**kwargs):
        return FakeStream()

    async def fake_run(*, starting_agent, input, session, run_config):
        chat_started.set()
        return SimpleNamespace(final_output="second reply")

    monkeypatch.setattr("app.services.chat.Runner.run_streamed", fake_run_streamed)
    monkeypatch.setattr("app.services.chat.Runner.run", fake_run)
    service = ChatService(tmp_path / "sessions.db")

    async def exercise():
        stream_task = asyncio.create_task(_collect_stream(service.stream("abc", "first")))
        await stream_started.wait()
        chat_task = asyncio.create_task(service.chat("abc", "second"))
        await asyncio.sleep(0)
        assert not chat_started.is_set()
        release_stream.set()
        await stream_task
        await chat_task

    asyncio.run(exercise())
    assert chat_started.is_set()
    assert service._session_gates == {}


async def _collect_stream(events):
    return [event async for event in events]


def test_chat_stream_close_cancels_run_and_releases_session(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    stream_run = None

    class FakeStream:
        final_output = None
        is_complete = False
        cancelled = False

        async def stream_events(self):
            if self.cancelled:
                return
            yield SimpleNamespace(
                type="raw_response_event",
                data=ResponseTextDeltaEvent(
                    type="response.output_text.delta",
                    content_index=0,
                    delta="partial",
                    item_id="item_1",
                    logprobs=[],
                    output_index=0,
                    sequence_number=1,
                ),
            )
            await asyncio.Event().wait()

        def cancel(self):
            self.cancelled = True
            self.is_complete = True

    def fake_run_streamed(**kwargs):
        nonlocal stream_run
        stream_run = FakeStream()
        return stream_run

    monkeypatch.setattr("app.services.chat.Runner.run_streamed", fake_run_streamed)
    service = ChatService(tmp_path / "sessions.db")

    async def exercise():
        events = service.stream("abc", "Hi")
        assert (await anext(events)).type == "started"
        assert (await anext(events)).delta == "partial"
        await events.aclose()

    asyncio.run(exercise())
    assert stream_run is not None and stream_run.cancelled
    assert service._session_gates == {}


def test_chat_stream_emits_error_after_sdk_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)

    class FailedStream:
        is_complete = False

        async def stream_events(self):
            if self.is_complete:
                return
            raise RuntimeError("provider details")
            yield

        def cancel(self):
            self.is_complete = True

    monkeypatch.setattr(
        "app.services.chat.Runner.run_streamed", lambda **kwargs: FailedStream()
    )
    service = ChatService(tmp_path / "sessions.db")

    events = asyncio.run(_collect_stream(service.stream("abc", "Hi")))

    assert [event.type for event in events] == ["started", "error"]
    assert events[-1].message == "Chat failed"
    assert "provider details" not in repr(events[-1])
    assert service._session_gates == {}


def test_chat_service_allows_different_sessions_to_overlap(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(settings, "openai_tracing_api_key", None)
    first_started = asyncio.Event()
    release_first = asyncio.Event()
    second_started = asyncio.Event()

    async def fake_run(*, starting_agent, input, session, run_config):
        if session.session_id == "first":
            first_started.set()
            await release_first.wait()
        else:
            second_started.set()
        return SimpleNamespace(final_output="reply")

    monkeypatch.setattr("app.services.chat.Runner.run", fake_run)
    service = ChatService(tmp_path / "sessions.db")

    async def exercise():
        first = asyncio.create_task(service.chat("first", "Hi"))
        await first_started.wait()
        second = asyncio.create_task(service.chat("second", "Hi"))
        await asyncio.wait_for(second_started.wait(), timeout=1)
        release_first.set()
        await asyncio.gather(first, second)

    asyncio.run(exercise())
    assert service._session_gates == {}
