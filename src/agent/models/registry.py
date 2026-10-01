from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_MODELS_PATH = Path(__file__).resolve().parent / "profiles" / "models.yaml"


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model: str
    settings: dict[str, Any]


class ModelRegistry:
    def __init__(self, profiles_path: Path = DEFAULT_MODELS_PATH) -> None:
        self._profiles = self._load_profiles(profiles_path)

    @staticmethod
    def _load_profiles(path: Path) -> dict[str, ModelProfile]:
        with path.open(encoding="utf-8") as profile_file:
            config = yaml.safe_load(profile_file) or {}

        profiles_config = config.get("profiles") if isinstance(config, dict) else None
        if not isinstance(profiles_config, dict):
            raise ValueError(f"model profile file must contain a 'profiles' mapping: {path}")

        profiles: dict[str, ModelProfile] = {}
        for name, definition in profiles_config.items():
            if not isinstance(definition, dict):
                raise ValueError(f"model profile '{name}' must be a mapping")

            model = definition.get("model")
            settings = definition.get("settings", {})
            if not isinstance(model, str) or not model:
                raise ValueError(f"model profile '{name}' must define a model")
            if not isinstance(settings, dict):
                raise ValueError(f"model profile '{name}' settings must be a mapping")

            profiles[name] = ModelProfile(
                name=name,
                model=model,
                settings=settings,
            )

        return profiles

    def get(self, profile_name: str) -> ModelProfile:
        try:
            return self._profiles[profile_name]
        except KeyError as exc:
            raise LookupError(f"unknown model profile: {profile_name}") from exc
