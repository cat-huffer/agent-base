"""将自然语言数据问题转换为 SQL 的 Agent。"""

from agents import Agent

from agent.models.router import ModelRouter, model_router
from agent.prompts.render import PromptRender


def create_nl2sql_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> Agent:
    """创建只生成 SQL、不执行数据库查询的 Agent。"""
    model_router_instance = router if router is not None else model_router
    renderer = prompt_renderer if prompt_renderer is not None else PromptRender()
    profile = model_router_instance.resolve("nl2sql")
    return Agent(
        name="NL2SQL",
        handoff_description="将自然语言数据查询需求转换为 SQL；需要已知表结构，不执行查询。",
        instructions=renderer.render("nl2sql"),
        model=profile.model,
        model_settings=profile.settings,
    )
