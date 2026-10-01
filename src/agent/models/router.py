from pathlib import Path

import yaml

from agent.models.registry import ModelProfile, ModelRegistry

DEFAULT_ROUTES_PATH = Path(__file__).resolve().parent / "profiles" / "router.yaml"


class ModelRouter:
    def __init__(
        self,
        registry: ModelRegistry | None = None,
        routes_path: Path = DEFAULT_ROUTES_PATH,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self._routes = self._load_routes(routes_path)

    @staticmethod
    def _load_routes(path: Path) -> dict[str, str]:
        with path.open(encoding="utf-8") as routes_file:
            config = yaml.safe_load(routes_file) or {}

        routes = config.get("routes") if isinstance(config, dict) else None
        if not isinstance(routes, dict):
            raise ValueError(f"model route file must contain a 'routes' mapping: {path}")

        profiles: dict[str, str] = {}
        for name, definition in routes.items():
            profile_name = definition.get("profile") if isinstance(definition, dict) else None
            if not isinstance(profile_name, str) or not profile_name:
                raise ValueError(f"model route '{name}' must define a profile")
            profiles[name] = profile_name

        return profiles

    def resolve(self, route_name: str) -> ModelProfile:
        try:
            profile_name = self._routes[route_name]
        except KeyError as exc:
            raise LookupError(f"unknown model route: {route_name}") from exc
        return self.registry.get(profile_name)


model_router = ModelRouter()
