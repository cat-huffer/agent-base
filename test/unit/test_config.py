from pathlib import Path

from app.config import PROJECT_ROOT, Settings, settings


def test_project_settings_have_agent_defaults() -> None:
    assert Settings(_env_file=None).app_env == "development"
    assert Settings(_env_file=None).default_model_profile == "default"
    assert settings.default_model_profile == "default"
    assert PROJECT_ROOT == Path.cwd().resolve()


def test_project_settings_do_not_expose_api_key() -> None:
    assert "openai_api_key" not in Settings.model_fields


def test_tracing_key_is_loaded_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_TRACING_API_KEY", "test-tracing-key")
    assert Settings(_env_file=None).openai_tracing_api_key == "test-tracing-key"
