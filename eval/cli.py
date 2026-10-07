import argparse
import sys
from pathlib import Path

import yaml

from eval.core.trial import Trial
from eval.runner import run_suite_sync, suite_task_pass_rate, summarize_task_trials


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an agent evaluation suite")
    parser.add_argument(
        "--suite",
        type=Path,
        default=Path("eval/suites/regression.yaml"),
        help="Path to the suite YAML file",
    )
    parser.add_argument("--output", type=Path, help="Path for the JSONL trial report")
    args = parser.parse_args()

    suite_data = yaml.safe_load(args.suite.read_text(encoding="utf-8"))
    trials = run_suite_sync(args.suite, args.output)
    trial_pass_rate = sum(trial.passed for trial in trials) / len(trials) if trials else 0.0
    task_summaries = summarize_task_trials(trials)
    task_pass_rate = suite_task_pass_rate(trials)
    threshold = float(suite_data.get("acceptance", {}).get("required_task_pass_rate", 1.0))
    result_path = args.output or Path.cwd() / ".data" / "eval" / f"{suite_data['id']}.jsonl"
    print(f"Trials: {len(trials)}; trial pass rate: {trial_pass_rate:.1%}")
    pass_k_tasks = sum(bool(summary["pass_k"]) for summary in task_summaries.values())
    total_tasks = len(task_summaries)
    pass_k_rate = pass_k_tasks / total_tasks if total_tasks else 0.0
    print(f"Mean per-task pass rate: {task_pass_rate:.1%}; required: {threshold:.1%}")
    print(f"pass^k (all repeats pass): {pass_k_tasks}/{total_tasks} tasks ({pass_k_rate:.1%})")
    print("Per-task results:")
    trials_by_task: dict[str, list[Trial]] = {}
    for trial in trials:
        trials_by_task.setdefault(trial.task_id, []).append(trial)
    for task_id, summary in task_summaries.items():
        passed = int(summary["passed_trials"])
        total = int(summary["total_trials"])
        consistent = "yes" if summary["pass_k"] else "no"
        print(
            f"  {task_id}: {passed}/{total} ({float(summary['pass_rate']):.1%}); "
            f"pass^{total}={consistent}"
        )
        for trial in trials_by_task[task_id]:
            if not trial.passed:
                print(
                    f"    failed trial #{trial.trial_index}: "
                    f"target={trial.handoff_target}, handoffs={trial.handoff_count}, "
                    f"trace_id={trial.trace_id}"
                )
                if trial.error:
                    print(f"      error={trial.error}")
    print(f"Results: {result_path}")
    return 0 if task_pass_rate >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
