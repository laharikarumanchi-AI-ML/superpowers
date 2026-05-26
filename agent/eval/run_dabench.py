import argparse
import json
import os
import time
import uuid
from pathlib import Path

from agent.orchestrator import run
from agent.llm_client import GroqClient
from agent.eval.scorers.infiagent.eval_closed_form import evaluate_responses


def load_tasks(questions_jsonl: Path, labels_jsonl: Path,
               data_dir: Path, subset: int | None) -> list[dict]:
    """Load DABench tasks, joining questions + labels on `id`."""
    labels_by_id: dict[int, dict] = {}
    for line in labels_jsonl.read_text().splitlines():
        if not line.strip():
            continue
        lab = json.loads(line)
        labels_by_id[lab["id"]] = lab

    tasks: list[dict] = []
    for line in questions_jsonl.read_text().splitlines():
        if not line.strip():
            continue
        q = json.loads(line)
        lab = labels_by_id.get(q["id"])
        if lab is None:
            continue  # unanswered task — skip
        tasks.append({
            **q,
            "_data_path": str(data_dir / q["file_name"]),
            "common_answers": lab["common_answers"],
        })
    if subset is not None:
        tasks = tasks[:subset]
    return tasks


def _make_client(provider: str, model: str | None):
    if provider == "groq":
        return GroqClient(api_key=os.environ["GROQ_API_KEY"],
                          model=model or "llama-3.3-70b-versatile")
    if provider == "gemini":
        from agent.llm_client import GeminiClient
        return GeminiClient(api_key=os.environ["GEMINI_API_KEY"],
                            model=model or "gemini-2.0-flash")
    raise ValueError(f"unknown provider: {provider}")


def run_eval(questions_jsonl: Path, labels_jsonl: Path, data_dir: Path,
             results_path: Path, subset: int | None, model: str | None,
             retry: bool, provider: str = "groq") -> None:
    llm = _make_client(provider, model)
    tasks = load_tasks(questions_jsonl, labels_jsonl, data_dir, subset)

    done_ids: set[int] = set()
    results: list[dict] = []
    if results_path.exists():
        existing = json.loads(results_path.read_text())
        results = existing["results"]
        done_ids = {r["task_id"] for r in results}

    for i, task in enumerate(tasks):
        if task["id"] in done_ids:
            continue
        t0 = time.time()
        try:
            agent_result = run(
                task["question"], task["_data_path"], llm,
                retry_on_failure=retry,
                llm_kwargs={"temperature": 0},
                constraints=task.get("constraints", ""),
                format_constraint=task.get("format", ""),
            )
            results.append({
                "task_id": task["id"],
                "predicted_response": agent_result.answer or "",
                "common_answers": task["common_answers"],
                "steps": agent_result.steps_taken,
                "success": agent_result.success,
                "failure_reason": agent_result.failure_reason,
                "wall_seconds": round(time.time() - t0, 2),
                "model": model or "default",
                "provider": provider,
                "retry": retry,
            })
        except Exception as exc:
            results.append({"task_id": task["id"], "error": str(exc),
                            "provider": provider, "retry": retry})

        results_path.write_text(json.dumps({
            "run_id": results_path.stem,
            "results": results,
        }, indent=2))
        print(f"[{i+1}/{len(tasks)}] task {task['id']}: done")


def score_run(results_path: Path) -> dict:
    """Apply the official scorer to a completed run. Returns metric dict.

    The upstream `evaluate_responses` returns per-task records shaped like
        {"id": ..., "label_answers": {...}, "predicted_answers": {...},
         "correctness": {ans_name: bool, ...}}
    A task is fully correct when every value in `correctness` is True.
    """
    data = json.loads(results_path.read_text())
    labels = [{"id": r["task_id"], "common_answers": r["common_answers"]}
              for r in data["results"] if "common_answers" in r]
    responses = [{"id": r["task_id"], "response": r["predicted_response"]}
                 for r in data["results"] if "predicted_response" in r]
    scored = evaluate_responses(labels, responses)
    n = len(scored)
    abq_correct = sum(
        1 for s in scored
        if "correctness" in s and s["correctness"]
        and all(s["correctness"].values())
    )
    return {"ABQ": abq_correct / n if n else 0.0,
            "n_tasks": n, "abq_correct": abq_correct}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True, type=Path)
    parser.add_argument("--labels", required=True, type=Path)
    parser.add_argument("--data-dir", required=True, type=Path)
    parser.add_argument("--subset", type=int, default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--provider", choices=["groq", "gemini"], default="groq")
    parser.add_argument("--no-retry", action="store_true")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--score-only", action="store_true",
                        help="skip the run; just score the existing results file")
    args = parser.parse_args()

    run_id = args.run_id or f"run-{uuid.uuid4().hex[:8]}"
    results_path = Path(__file__).parent / "results" / f"{run_id}.json"
    results_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.score_only:
        run_eval(args.questions, args.labels, args.data_dir, results_path,
                 subset=args.subset, model=args.model,
                 retry=not args.no_retry, provider=args.provider)

    metrics = score_run(results_path)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
