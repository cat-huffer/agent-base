import pytest

from agent.prompts.loader import PromptLoader
from agent.prompts.registry import PromptRegistry
from agent.prompts.render import PromptRender


def test_assistant_profile_renders_instructions() -> None:
    registry = PromptRegistry()

    profile = registry.get("assistant")
    assert profile.id == "assistant"
    assert profile.version == "1.0.0"
    assert profile.template == "assistant/system.md"
    assert PromptRender(registry).render("assistant") == (
        "You are a helpful AI assistant.\n\n"
        "Answer the user's questions accurately, clearly, and concisely."
    )


def test_unknown_prompt_raises_clear_error() -> None:
    with pytest.raises(LookupError, match="unknown prompt profile: missing"):
        PromptRegistry().get("missing")


def test_renderer_substitutes_variables_without_interpreting_json_braces(tmp_path) -> None:
    profiles = tmp_path / "profiles"
    templates = tmp_path / "templates"
    profiles.mkdir()
    templates.mkdir()
    (templates / "assistant").mkdir(parents=True)
    (profiles / "assistant.yaml").write_text(
        'id: assistant\nversion: "1.0.0"\ntemplate: assistant/system.md\n',
        encoding="utf-8",
    )
    (templates / "assistant" / "system.md").write_text(
        'Hello, ${name}! JSON: {"ok": true}', encoding="utf-8"
    )
    renderer = PromptRender(PromptRegistry(PromptLoader(profiles, templates)))

    assert renderer.render("assistant", {"name": "Ada"}) == 'Hello, Ada! JSON: {"ok": true}'
    with pytest.raises(ValueError, match="missing prompt variable: name"):
        renderer.render("assistant")


def test_registry_rejects_mismatched_profile_id(tmp_path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "assistant.yaml").write_text(
        'id: other\nversion: "1.0.0"\ntemplate: assistant/system.md\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="id must be 'assistant'"):
        PromptRegistry(PromptLoader(profiles)).get("assistant")
