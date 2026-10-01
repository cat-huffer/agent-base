from collections.abc import Mapping
from string import Template

from agent.prompts.registry import PromptProfile, PromptRegistry


class PromptRender:
    def __init__(self, registry: PromptRegistry | None = None) -> None:
        self.registry = registry or PromptRegistry()

    def render(self, name: str, variables: Mapping[str, str] | None = None) -> str:
        profile = self.registry.get(name)
        return self.render_profile(profile, variables)

    def render_profile(
        self, profile: PromptProfile, variables: Mapping[str, str] | None = None
    ) -> str:
        template = self.registry.loader.load_template(profile.template)
        try:
            return Template(template).substitute(variables or {})
        except KeyError as exc:
            raise ValueError(f"missing prompt variable: {exc.args[0]}") from exc
