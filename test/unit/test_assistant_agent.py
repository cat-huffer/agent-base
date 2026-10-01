from unittest.mock import Mock

from agents import Agent

from agent.agents.assistant import assemble_assistant_agent, create_assistant_agent
from agent.models.registry import ModelRegistry
from agent.models.router import ModelRouter
from agent.prompts.registry import PromptProfile
from agent.prompts.render import PromptRender


def test_create_assistant_agent_uses_chat_model_and_rendered_prompt() -> None:
    assistant = create_assistant_agent()

    assert isinstance(assistant, Agent)
    assert assistant.name == "Assistant"
    assert assistant.model == "deepseek-flash"
    assert assistant.instructions == PromptRender().render("assistant")
    assert assistant.tools == []
    assert assistant.handoffs == []


def test_create_assistant_agent_passes_non_default_model_settings(tmp_path) -> None:
    models_path = tmp_path / "models.yaml"
    routes_path = tmp_path / "router.yaml"
    models_path.write_text(
        "profiles:\n  reasoning:\n    model: deepseek-v4-pro\n"
        "    settings:\n      reasoning:\n        effort: high\n",
        encoding="utf-8",
    )
    routes_path.write_text("routes:\n  chat:\n    profile: reasoning\n", encoding="utf-8")
    router = ModelRouter(ModelRegistry(models_path), routes_path)

    prompt_renderer = Mock(spec=PromptRender)
    prompt_renderer.registry = Mock()
    prompt_profile = PromptProfile("assistant", "1.0.0", "assistant/system.md")
    prompt_renderer.registry.get.return_value = prompt_profile
    prompt_renderer.render_profile.return_value = "Injected instructions"
    assistant = create_assistant_agent(router=router, prompt_renderer=prompt_renderer)

    assert assistant.model == "deepseek-v4-pro"
    assert assistant.instructions == "Injected instructions"
    assert assistant.model_settings.reasoning is not None
    assert assistant.model_settings.reasoning.effort == "high"
    prompt_renderer.registry.get.assert_called_once_with("assistant")
    prompt_renderer.render_profile.assert_called_once_with(prompt_profile)


def test_assistant_assembly_uses_profiles_for_agent_and_metadata() -> None:
    router = Mock(spec=ModelRouter)
    model_profile = ModelRegistry().get("default")
    router.resolve.return_value = model_profile
    prompt_renderer = Mock(spec=PromptRender)
    prompt_renderer.registry = Mock()
    prompt_profile = PromptProfile("assistant", "1.0.0", "assistant/system.md")
    prompt_renderer.registry.get.return_value = prompt_profile
    prompt_renderer.render_profile.return_value = "Injected instructions"

    assembly = assemble_assistant_agent(router=router, prompt_renderer=prompt_renderer)

    assert assembly.agent.model == assembly.model_profile.model
    assert assembly.agent.instructions == "Injected instructions"
    assert assembly.model_profile is model_profile
    assert assembly.prompt_profile is prompt_profile
    router.resolve.assert_called_once_with("chat")
    prompt_renderer.registry.get.assert_called_once_with("assistant")
    prompt_renderer.render_profile.assert_called_once_with(prompt_profile)
