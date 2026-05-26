import json
from pathlib import Path
from agent.eval.run_dabench import load_tasks, score_run


def test_load_tasks_joins_questions_and_labels(tmp_path: Path):
    questions = tmp_path / "q.jsonl"
    labels = tmp_path / "l.jsonl"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    questions.write_text("\n".join([
        json.dumps({"id": 1, "question": "Q1?", "file_name": "a.csv",
                    "constraints": "c1", "format": "@x[float]"}),
        json.dumps({"id": 2, "question": "Q2?", "file_name": "b.csv",
                    "constraints": "c2", "format": "@y[int]"}),
    ]))
    labels.write_text("\n".join([
        json.dumps({"id": 1, "common_answers": [["x", "1.5"]]}),
        json.dumps({"id": 2, "common_answers": [["y", "42"]]}),
    ]))
    tasks = load_tasks(questions, labels, data_dir, subset=None)
    assert len(tasks) == 2
    assert tasks[0]["question"] == "Q1?"
    assert tasks[0]["_data_path"].endswith("a.csv")
    assert tasks[0]["common_answers"] == [["x", "1.5"]]


def test_load_tasks_subset(tmp_path: Path):
    questions = tmp_path / "q.jsonl"
    labels = tmp_path / "l.jsonl"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    questions.write_text("\n".join(
        json.dumps({"id": i, "question": "?", "file_name": "x.csv",
                    "constraints": "", "format": ""}) for i in range(5)
    ))
    labels.write_text("\n".join(
        json.dumps({"id": i, "common_answers": [["x", "0"]]}) for i in range(5)
    ))
    tasks = load_tasks(questions, labels, data_dir, subset=3)
    assert len(tasks) == 3


def test_load_tasks_skips_unanswered(tmp_path: Path):
    questions = tmp_path / "q.jsonl"
    labels = tmp_path / "l.jsonl"
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    questions.write_text("\n".join([
        json.dumps({"id": 1, "question": "?", "file_name": "a.csv",
                    "constraints": "", "format": ""}),
        json.dumps({"id": 2, "question": "?", "file_name": "b.csv",
                    "constraints": "", "format": ""}),
    ]))
    labels.write_text(json.dumps({"id": 1, "common_answers": [["x", "1"]]}))
    tasks = load_tasks(questions, labels, data_dir, subset=None)
    assert len(tasks) == 1
    assert tasks[0]["id"] == 1


def test_score_run_smoke(tmp_path: Path):
    """End-to-end: a results file with a known good answer scores 1.0 ABQ."""
    results_path = tmp_path / "r.json"
    results_path.write_text(json.dumps({
        "run_id": "test",
        "results": [{
            "task_id": 1,
            "predicted_response": "<answer>@mean[1.5]</answer>",
            "common_answers": [["mean", "1.5"]],
        }],
    }))
    metrics = score_run(results_path)
    assert metrics["n_tasks"] == 1
    assert metrics["ABQ"] == 1.0
