from pathlib import Path

import yaml
from agents import Agent, HandoffOutputItem

from eval.core.trial import Trial
from eval.graders.registry import grade_task
from eval.runner import extract_handoff_target, suite_task_pass_rate, validate_trial_policy


def test_extract_router_handoff_target_from_sdk_run_items() -> None:
    router = Agent(name="Router", instructions="")
    nl2sql = Agent(name="NL2SQL", instructions="")
    specialist = Agent(name="Specialist", instructions="")
    items = [
        HandoffOutputItem(agent=router, raw_item={}, source_agent=router, target_agent=nl2sql),
        HandoffOutputItem(
            agent=nl2sql, raw_item={}, source_agent=nl2sql, target_agent=specialist
        ),
    ]

    assert extract_handoff_target(items) == "NL2SQL"


def test_local_handoff_grader_checks_expected_target() -> None:
    task = {
        "expected": {"handoff_target": "NL2SQL"},
        "graders": [
            {
                "id": "expected_handoff_target",
                "provider": "local",
                "target": "trial.handoff_target",
                "config": {"equals_expected": "expected.handoff_target"},
                "pass_threshold": 1.0,
                "required": True,
            }
        ],
    }

    results = grade_task(task, {"handoff_target": "General"})

    assert results == [
        {"id": "expected_handoff_target", "score": 0.0, "passed": False, "required": True}
    ]


def test_task_without_graders_is_rejected() -> None:
    task = {"id": "missing-graders", "expected": {"handoff_target": "NL2SQL"}}

    try:
        grade_task(task, {"handoff_target": "NL2SQL"})
    except ValueError as exc:
        assert "at least one grader" in str(exc)
    else:
        raise AssertionError("a task without graders must be rejected")


def test_task_with_only_optional_graders_is_rejected() -> None:
    task = {
        "id": "optional-graders-only",
        "expected": {"handoff_target": "NL2SQL"},
        "graders": [
            {
                "id": "expected_handoff_target",
                "provider": "local",
                "target": "trial.handoff_target",
                "config": {"equals_expected": "expected.handoff_target"},
                "required": False,
            }
        ],
    }

    try:
        grade_task(task, {"handoff_target": "NL2SQL"})
    except ValueError as exc:
        assert "at least one required grader" in str(exc)
    else:
        raise AssertionError("a task without required graders must be rejected")


def test_trial_policy_requires_positive_repetition_count() -> None:
    try:
        validate_trial_policy({"id": "bad-suite", "trial_policy": {"repetitions": 0}})
    except ValueError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("zero repetitions must be rejected")


def test_router_regression_task_uses_expected_target_as_grader_reference() -> None:
    task_path = Path(__file__).parents[2] / "eval/datasets/module/router/count_customs_records.yaml"
    task = yaml.safe_load(task_path.read_text(encoding="utf-8"))

    assert task["expected"]["handoff_target"] == "NL2SQL"
    assert len(task["graders"]) == 2
    assert task["graders"][0]["config"]["equals_expected"] == "expected.handoff_target"


def test_suite_task_pass_rate_weights_tasks_equally() -> None:
    trials = [
        Trial("task-a", 1, "trace-a1", "NL2SQL", "NL2SQL", [], True, 10),
        Trial("task-a", 2, "trace-a2", "NL2SQL", "General", [], False, 10),
        Trial("task-b", 1, "trace-b1", "General", "General", [], True, 10),
    ]

    assert suite_task_pass_rate(trials) == 0.75
