"""处理普通对话的 Agent。"""

from agents import Agent

from agent.models.router import ModelRouter, model_router
from agent.prompts.render import PromptRender


def create_general_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> Agent:
    """使用通用对话模型和提示词创建 Agent。"""
    model_router_instance = router if router is not None else model_router
    renderer = prompt_renderer if prompt_renderer is not None else PromptRender()
    profile = model_router_instance.resolve("chat")
    return Agent(
        name="General",
        handoff_description="处理普通对话、解释和不涉及数据库查询的常见问题。",
        instructions=renderer.render("general"),
        model=profile.model,
        model_settings=profile.settings,
    )
