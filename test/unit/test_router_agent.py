from unittest.mock import Mock

from agents import Agent

from agent.agents.router import assemble_router_agent, create_router_agent
from agent.models.registry import ModelRegistry
from agent.models.router import ModelRouter
from agent.prompts.registry import PromptProfile
from agent.prompts.render import PromptRender


def test_router_exposes_only_the_two_supported_handoff_destinations() -> None:
    router_agent = create_router_agent()

    assert [agent.name for agent in router_agent.handoffs] == ["NL2SQL", "General"]
    assert all(agent.handoffs == [] for agent in router_agent.handoffs)
    assert "查询条件不完整" in router_agent.handoffs[0].handoff_description
    assert "实际业务记录" in router_agent.handoffs[0].handoff_description
    assert "业务概念" in router_agent.handoffs[1].handoff_description
    assert "SQL 和数据库知识" in router_agent.handoffs[1].handoff_description


def test_create_router_agent_uses_routing_model_and_rendered_prompt() -> None:
    router_agent = create_router_agent()

    assert isinstance(router_agent, Agent)
    assert router_agent.name == "Router"
    assert router_agent.model == "deepseek-flash"
    assert "入口路由 Agent" in router_agent.instructions
    assert router_agent.tools == []
    assert [agent.name for agent in router_agent.handoffs] == ["NL2SQL", "General"]


def test_router_agent_passes_model_settings_and_specialist_handoffs(tmp_path) -> None:
    models_path = tmp_path / "models.yaml"
    routes_path = tmp_path / "routes.yaml"
    models_path.write_text(
        "profiles:\n  reasoning:\n    model: deepseek-v4-pro\n"
        "    settings:\n      reasoning:\n        effort: high\n",
        encoding="utf-8",
    )
    routes_path.write_text(
        "routes:\n  routing:\n    profile: reasoning\n"
        "  nl2sql:\n    profile: reasoning\n  chat:\n    profile: reasoning\n",
        encoding="utf-8",
    )
    model_router = ModelRouter(ModelRegistry(models_path), routes_path)

    prompt_renderer = Mock(spec=PromptRender)
    prompt_renderer.registry = Mock()
    prompt_profile = PromptProfile("router", "2.0.0", "router/system.md")
    prompt_renderer.registry.get.return_value = prompt_profile
    prompt_renderer.render_profile.return_value = "路由提示词"
    prompt_renderer.render.side_effect = lambda name: f"{name} 提示词"

    assembly = assemble_router_agent(router=model_router, prompt_renderer=prompt_renderer)

    assert assembly.agent.model == "deepseek-v4-pro"
    assert assembly.agent.instructions == "路由提示词"
    assert [agent.name for agent in assembly.agent.handoffs] == ["NL2SQL", "General"]
    assert assembly.model_profile.name == "reasoning"
    assert assembly.prompt_profile is prompt_profile
    prompt_renderer.registry.get.assert_called_once_with("router")
    prompt_renderer.render_profile.assert_called_once_with(prompt_profile)
