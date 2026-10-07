from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Trial:
    task_id: str
    trial_index: int
    trace_id: str
    expected_handoff_target: str
    handoff_target: str | None
    grader_results: list[dict[str, Any]]
    passed: bool
    elapsed_ms: int
    handoff_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
