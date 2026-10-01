from dataclasses import dataclass

from agent.prompts.loader import PromptLoader


@dataclass(frozen=True)
class PromptProfile:
    id: str
    version: str
    template: str


class PromptRegistry:
    def __init__(self, loader: PromptLoader | None = None) -> None:
        self.loader = loader or PromptLoader()

    def get(self, name: str) -> PromptProfile:
        if not name.isidentifier() or not (self.loader.profiles_path / f"{name}.yaml").is_file():
            raise LookupError(f"unknown prompt profile: {name}")
        config = self.loader.load_profile(name)
        if not isinstance(config, dict):
            raise ValueError(f"prompt profile '{name}' must be a mapping")
        if config.get("id") != name:
            raise ValueError(f"prompt profile '{name}' id must be '{name}'")
        version = config.get("version")
        template = config.get("template")
        if not isinstance(version, str) or not version:
            raise ValueError(f"prompt profile '{name}' must define a version")
        if not isinstance(template, str) or not template:
            raise ValueError(f"prompt profile '{name}' must define a template")
        return PromptProfile(id=name, version=version, template=template)
