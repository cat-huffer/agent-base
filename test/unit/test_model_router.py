import pytest

from agent.models.registry import ModelProfile, ModelRegistry
from agent.models.router import ModelRouter, model_router


def test_chat_route_resolves_to_default_profile() -> None:
    profile = model_router.resolve("chat")

    assert isinstance(profile, ModelProfile)
    assert profile.name == "default"
    assert profile.model == "deepseek-flash"
    assert profile.settings == {
        "reasoning": {"effort": "none"},
        "verbosity": "low",
    }


def test_registry_gets_profile_without_routing() -> None:
    profile = ModelRegistry().get("reasoning")

    assert profile.name == "reasoning"
    assert profile.model == "deepseek-v4-pro"
    assert profile.settings["reasoning"] == {"effort": "medium"}


def test_registry_defaults_missing_settings_to_empty_mapping(tmp_path) -> None:
    profiles_path = tmp_path / "models.yaml"
    profiles_path.write_text("profiles:\n  default:\n    model: deepseek-flash\n", encoding="utf-8")

    assert ModelRegistry(profiles_path).get("default").settings == {}


def test_unknown_route_raises_clear_error() -> None:
    with pytest.raises(LookupError, match="unknown model route"):
        ModelRouter().resolve("missing")
