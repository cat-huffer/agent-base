import pytest

from agent.prompts.loader import PromptLoader
from agent.prompts.registry import PromptRegistry
from agent.prompts.render import PromptRender


def test_router_profile_renders_instructions() -> None:
    registry = PromptRegistry()

    profile = registry.get("router")
    assert profile.id == "router"
    assert profile.version == "1.0.0"
    assert profile.template == "router/system.md"
    rendered = PromptRender(registry).render("router")
    assert "<role>" in rendered
    assert "入口路由 Agent" in rendered
    assert "handoff" in rendered


def test_unknown_prompt_raises_clear_error() -> None:
    with pytest.raises(LookupError, match="unknown prompt profile: missing"):
        PromptRegistry().get("missing")


def test_renderer_substitutes_variables_without_interpreting_json_braces(tmp_path) -> None:
    profiles = tmp_path / "profiles"
    templates = tmp_path / "templates"
    profiles.mkdir()
    templates.mkdir()
    (templates / "router").mkdir(parents=True)
    (profiles / "router.yaml").write_text(
        'id: router\nversion: "1.0.0"\ntemplate: router/system.md\n',
        encoding="utf-8",
    )
    (templates / "router" / "system.md").write_text(
        'Hello, ${name}! JSON: {"ok": true}', encoding="utf-8"
    )
    renderer = PromptRender(PromptRegistry(PromptLoader(profiles, templates)))

    assert renderer.render("router", {"name": "Ada"}) == 'Hello, Ada! JSON: {"ok": true}'
    with pytest.raises(ValueError, match="missing prompt variable: name"):
        renderer.render("router")


def test_registry_rejects_mismatched_profile_id(tmp_path) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "router.yaml").write_text(
        'id: other\nversion: "1.0.0"\ntemplate: router/system.md\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="id must be 'router'"):
        PromptRegistry(PromptLoader(profiles)).get("router")
