import asyncio
import json
import time
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml
from agents import HandoffOutputItem, RunConfig, Runner, gen_trace_id

from agent.agents.router import assemble_router_agent
from agent.models.router import model_router
from agent.prompts.render import PromptRender
from app.config import settings
from eval.core.trial import Trial
from eval.graders.registry import grade_task, validate_task_graders


def extract_handoff_target(items: Iterable[Any]) -> str | None:
    """Return the destination of the Router's first completed SDK handoff."""
    for item in items:
        if (
            isinstance(item, HandoffOutputItem)
            and item.source_agent.name == "Router"
        ):
            return item.target_agent.name
    return None


def count_router_handoffs(items: Iterable[Any]) -> int:
    """Count completed SDK handoffs initiated by the Router."""
    return sum(
        1
        for item in items
        if isinstance(item, HandoffOutputItem) and item.source_agent.name == "Router"
    )


def suite_task_pass_rate(trials: Iterable[Trial]) -> float:
    """Average each task's pass rate so tasks with more trials are not overweighted."""
    summaries = summarize_task_trials(trials)
    if not summaries:
        return 0.0
    return sum(float(summary["pass_rate"]) for summary in summaries.values()) / len(summaries)


def summarize_task_trials(trials: Iterable[Trial]) -> dict[str, dict[str, int | float | bool]]:
    """Return per-task pass rates and whether every repeated trial passed (pass^k)."""
    grouped: dict[str, list[Trial]] = {}
    for trial in trials:
        grouped.setdefault(trial.task_id, []).append(trial)

    summaries: dict[str, dict[str, int | float | bool]] = {}
    for task_id, task_trials in grouped.items():
        passed = sum(trial.passed for trial in task_trials)
        total = len(task_trials)
        summaries[task_id] = {
            "passed_trials": passed,
            "total_trials": total,
            "pass_rate": passed / total,
            "pass_k": passed == total,
        }
    return summaries


def _read_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a YAML mapping in {path}")
    return value


def validate_trial_policy(suite: dict[str, Any]) -> tuple[int, int]:
    """Validate and return a Suite's repetitions and parallelism settings."""
    suite_id = suite.get("id", "<unknown>")
    policy = suite.get("trial_policy", {})
    if not isinstance(policy, dict):
        raise ValueError(f"Suite '{suite_id}' trial_policy must be a mapping")

    repetitions = policy.get("repetitions", 1)
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError(f"Suite '{suite_id}' repetitions must be a positive integer")

    parallelism = policy.get("parallelism", 1)
    if isinstance(parallelism, bool) or not isinstance(parallelism, int):
        raise ValueError(f"Suite '{suite_id}' parallelism must be an integer")
    if parallelism != 1:
        raise ValueError("the eval runner currently supports trial_policy.parallelism: 1 only")

    return repetitions, parallelism


def _load_suite_tasks(
    suite_path: Path, ancestors: tuple[Path, ...] = ()
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Load tasks from a Suite and any child Suites it includes."""
    suite_path = suite_path.resolve()
    if suite_path in ancestors:
        chain = " -> ".join(str(path) for path in (*ancestors, suite_path))
        raise ValueError(f"cyclic suite reference: {chain}")

    suite = _read_yaml(suite_path)
    task_refs = suite.get("tasks", [])
    child_suite_refs = suite.get("suites", [])
    if not isinstance(task_refs, list) or not isinstance(child_suite_refs, list):
        raise ValueError(f"'tasks' and 'suites' must be lists in {suite_path}")
    if not task_refs and not child_suite_refs:
        raise ValueError(f"Suite must define at least one task or child suite: {suite_path}")
    if task_refs:
        validate_trial_policy(suite)

    loaded: list[tuple[dict[str, Any], dict[str, Any]]] = []
    next_ancestors = (*ancestors, suite_path)
    for suite_ref in child_suite_refs:
        if not isinstance(suite_ref, dict) or not isinstance(suite_ref.get("path"), str):
            raise ValueError(f"each suite reference must define a path in {suite_path}")
        child_path = (suite_path.parent / suite_ref["path"]).resolve()
        loaded.extend(_load_suite_tasks(child_path, next_ancestors))

    for task_ref in task_refs:
        if not isinstance(task_ref, dict) or not isinstance(task_ref.get("path"), str):
            raise ValueError(f"each task reference must define a path in {suite_path}")
        task_path = (suite_path.parent / task_ref["path"]).resolve()
        task = _read_yaml(task_path)
        validate_task_graders(task)
        loaded.append((suite, task))
    return loaded


async def _run_trial(
    *,
    suite: dict[str, Any],
    module_suite: dict[str, Any],
    task: dict[str, Any],
    trial_index: int,
    router: Any,
) -> Trial:
    trace_id = gen_trace_id()
    expected_target = task["expected"]["handoff_target"]
    trace_key = settings.openai_tracing_api_key
    run_config = RunConfig(
        workflow_name=f"eval-{suite['id']}",
        trace_id=trace_id,
        trace_metadata={
            "eval_suite": suite["id"],
            "eval_module_suite": module_suite["id"],
            "eval_task": task["id"],
            "trial_index": str(trial_index),
        },
        tracing_disabled=not bool(trace_key),
        tracing={"api_key": trace_key} if trace_key else None,
        trace_include_sensitive_data=False,
    )
    started = time.perf_counter()
    error = None
    handoff_target = None
    handoff_count = 0
    try:
        result = await Runner.run(
            starting_agent=router.agent,
            input=task["input"]["message"],
            run_config=run_config,
        )
        run_items = list(result.new_items)
        handoff_target = extract_handoff_target(run_items)
        handoff_count = count_router_handoffs(run_items)
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"

    elapsed_ms = round((time.perf_counter() - started) * 1000)
    trial_data = {"handoff_target": handoff_target, "handoff_count": handoff_count}
    grader_results = grade_task(task, trial_data)
    required_passed = all(
        grader["passed"] for grader in grader_results if grader["required"]
    )
    return Trial(
        task_id=task["id"],
        trial_index=trial_index,
        trace_id=trace_id,
        expected_handoff_target=expected_target,
        handoff_target=handoff_target,
        handoff_count=handoff_count,
        grader_results=grader_results,
        passed=required_passed and error is None,
        elapsed_ms=elapsed_ms,
        error=error,
    )


async def run_suite(suite_path: Path, output_path: Path | None = None) -> list[Trial]:
    suite_path = suite_path.resolve()
    suite = _read_yaml(suite_path)
    suite_tasks = _load_suite_tasks(suite_path)
    router = assemble_router_agent(router=model_router, prompt_renderer=PromptRender())
    trials: list[Trial] = []

    for module_suite, task in suite_tasks:
        repetitions, _ = validate_trial_policy(module_suite)
        if task.get("input", {}).get("session", "fresh") != "fresh":
            raise ValueError(f"task '{task.get('id')}' uses an unsupported session mode")
        for trial_index in range(1, repetitions + 1):
            trials.append(
                await _run_trial(
                    suite=suite,
                    module_suite=module_suite,
                    task=task,
                    trial_index=trial_index,
                    router=router,
                )
            )

    if output_path is None:
        output_path = Path.cwd() / ".data" / "eval" / f"{suite['id']}.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(trial.to_dict(), ensure_ascii=False) + "\n" for trial in trials),
        encoding="utf-8",
    )
    return trials


def run_suite_sync(suite_path: Path, output_path: Path | None = None) -> list[Trial]:
    return asyncio.run(run_suite(suite_path, output_path))
