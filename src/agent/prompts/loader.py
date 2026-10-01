from pathlib import Path

import yaml

DEFAULT_PROFILES_PATH = Path(__file__).resolve().parent / "profiles"
DEFAULT_TEMPLATES_PATH = Path(__file__).resolve().parent / "templates"


class PromptLoader:
    def __init__(
        self,
        profiles_path: Path = DEFAULT_PROFILES_PATH,
        templates_path: Path = DEFAULT_TEMPLATES_PATH,
    ) -> None:
        self.profiles_path = profiles_path
        self.templates_path = templates_path

    def load_profile(self, name: str) -> object:
        path = self.profiles_path / f"{name}.yaml"
        with path.open(encoding="utf-8") as profile_file:
            return yaml.safe_load(profile_file)

    def load_template(self, template: str) -> str:
        path = (self.templates_path / template).resolve()
        if not path.is_relative_to(self.templates_path.resolve()):
            raise ValueError(f"prompt template must be within templates directory: {template}")
        return path.read_text(encoding="utf-8").strip()
