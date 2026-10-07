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
        handoff_description=(
            "处理不需要读取本系统实际业务记录的请求，包括普通对话、SQL 和数据库知识、"
            "物流关务业务概念与流程解释，以及写作协助；"
            "也接收对本系统业务记录的写入请求，说明当前仅支持 SELECT 查询，不执行写入操作。"
        ),
        instructions=renderer.render("general"),
        model=profile.model,
        model_settings=profile.settings,
    )
