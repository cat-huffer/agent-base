"""入口路由 Agent：根据请求选择专业 Agent 并执行 handoff。"""

from dataclasses import dataclass

from agents import Agent

from agent.agents.general import create_general_agent
from agent.agents.nl2SQL import create_nl2sql_agent
from agent.models.registry import ModelProfile
from agent.models.router import ModelRouter, model_router
from agent.prompts.registry import PromptProfile
from agent.prompts.render import PromptRender


@dataclass(frozen=True)
class RouterAgentAssembly:
    """路由 Agent 及其模型配置。"""

    agent: Agent
    model_profile: ModelProfile
    prompt_profile: PromptProfile


def assemble_router_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> RouterAgentAssembly:
    """组装只向 General 和 NL2SQL 移交请求的入口 Agent。"""
    model_router_instance = router if router is not None else model_router
    model_profile = model_router_instance.resolve("routing")
    prompt_renderer = prompt_renderer if prompt_renderer is not None else PromptRender()
    prompt_profile = prompt_renderer.registry.get("router")
    instructions = prompt_renderer.render_profile(prompt_profile)
    handoffs = [
        create_nl2sql_agent(router=model_router_instance, prompt_renderer=prompt_renderer),
        create_general_agent(router=model_router_instance, prompt_renderer=prompt_renderer),
    ]

    agent = Agent(
        name="Router",
        instructions=instructions,
        model=model_profile.model,
        model_settings=model_profile.settings,
        handoffs=handoffs,
    )
    return RouterAgentAssembly(
        agent=agent,
        model_profile=model_profile,
        prompt_profile=prompt_profile,
    )


def create_router_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> Agent:
    """创建入口路由 Agent。"""
    return assemble_router_agent(
        router=router,
        prompt_renderer=prompt_renderer,
    ).agent
