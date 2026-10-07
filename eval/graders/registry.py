from collections.abc import Mapping
from typing import Any


def _value_at_path(data: Mapping[str, Any], path: str) -> Any:
    value: Any = data
    for part in path.split("."):
        if not isinstance(value, Mapping) or part not in value:
            raise ValueError(f"grader target path not found: {path}")
        value = value[part]
    return value


def validate_task_graders(task: Mapping[str, Any]) -> None:
    """Reject tasks whose graders cannot produce a required, supported score."""
    task_id = task.get("id", "<unknown>")
    graders = task.get("graders")
    if not isinstance(graders, list) or not graders:
        raise ValueError(f"task '{task_id}' must define at least one grader")

    grader_ids: set[str] = set()
    has_required_grader = False
    for index, grader in enumerate(graders, start=1):
        if not isinstance(grader, Mapping):
            raise ValueError(f"task '{task_id}' grader #{index} must be a mapping")

        grader_id = grader.get("id")
        if not isinstance(grader_id, str) or not grader_id.strip():
            raise ValueError(f"task '{task_id}' grader #{index} must define a non-empty id")
        if grader_id in grader_ids:
            raise ValueError(f"task '{task_id}' has duplicate grader id '{grader_id}'")
        grader_ids.add(grader_id)

        if grader.get("provider") != "local":
            raise ValueError(
                f"task '{task_id}' grader '{grader_id}' uses unsupported provider "
                f"'{grader.get('provider')}'"
            )

        target = grader.get("target")
        if not isinstance(target, str) or not target.startswith("trial."):
            raise ValueError(
                f"task '{task_id}' grader '{grader_id}' target must start with 'trial.'"
            )

        config = grader.get("config")
        expected_path = config.get("equals_expected") if isinstance(config, Mapping) else None
        if not isinstance(expected_path, str) or not expected_path:
            raise ValueError(
                f"task '{task_id}' grader '{grader_id}' must define "
                "config.equals_expected"
            )
        _value_at_path(task, expected_path)

        required = grader.get("required")
        if not isinstance(required, bool):
            raise ValueError(f"task '{task_id}' grader '{grader_id}' must define boolean required")
        has_required_grader = has_required_grader or required

        threshold = grader.get("pass_threshold", 1.0)
        if (
            isinstance(threshold, bool)
            or not isinstance(threshold, (int, float))
            or not 0.0 <= threshold <= 1.0
        ):
            raise ValueError(
                f"task '{task_id}' grader '{grader_id}' pass_threshold must be between 0 and 1"
            )

    if not has_required_grader:
        raise ValueError(f"task '{task_id}' must define at least one required grader")


def grade_task(task: Mapping[str, Any], trial: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Run the local equality graders declared by a task."""
    validate_task_graders(task)
    results: list[dict[str, Any]] = []
    for grader in task.get("graders", []):
        if grader.get("provider") != "local":
            raise ValueError(f"unsupported grader provider: {grader.get('provider')}")

        actual = _value_at_path({"trial": trial}, grader["target"])
        expected_path = grader.get("config", {}).get("equals_expected")
        if not isinstance(expected_path, str):
            raise ValueError(f"grader '{grader.get('id')}' must define config.equals_expected")
        expected = _value_at_path(task, expected_path)
        score = 1.0 if actual == expected else 0.0
        threshold = float(grader.get("pass_threshold", 1.0))
        results.append(
            {
                "id": grader["id"],
                "score": score,
                "passed": score >= threshold,
                "required": bool(grader.get("required", False)),
            }
        )
    return results
