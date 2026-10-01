from dataclasses import dataclass

from agents import Agent

from agent.models.registry import ModelProfile
from agent.models.router import ModelRouter, model_router
from agent.prompts.registry import PromptProfile
from agent.prompts.render import PromptRender


@dataclass(frozen=True)
class AssistantAssembly:
    agent: Agent
    model_profile: ModelProfile
    prompt_profile: PromptProfile


def assemble_assistant_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> AssistantAssembly:
    router = router if router is not None else model_router
    prompt_renderer = prompt_renderer if prompt_renderer is not None else PromptRender()
    model_profile = router.resolve("chat")
    prompt_profile = prompt_renderer.registry.get("assistant")
    instructions = prompt_renderer.render_profile(prompt_profile)
    agent = Agent(
        name="Assistant",
        instructions=instructions,
        model=model_profile.model,
        model_settings=model_profile.settings,
    )
    return AssistantAssembly(
        agent=agent, model_profile=model_profile, prompt_profile=prompt_profile
    )


def create_assistant_agent(
    *,
    router: ModelRouter | None = None,
    prompt_renderer: PromptRender | None = None,
) -> Agent:
    return assemble_assistant_agent(router=router, prompt_renderer=prompt_renderer).agent
