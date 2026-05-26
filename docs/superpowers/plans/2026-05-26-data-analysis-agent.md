# Data Analysis Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a code-as-action data-analysis agent that answers natural-language questions about CSV datasets by writing and executing Python in a sandboxed Jupyter kernel; evaluate it on InfiAgent-DABench.

**Architecture:** Five focused Python modules (`llm_client`, `sandbox`, `orchestrator`, `trace`, `eval/run_dabench`) plus a CLI entrypoint and a Streamlit demo. The agent loop is custom-written (no LangChain). Test-driven throughout: every module gets unit tests; one end-to-end test exercises the full loop against a mocked LLM. The MVP gate is reached at Task 12 (CLI + 80-task benchmark + working demo), at which point the portfolio site can begin its own plan.

**Tech Stack:** Python 3.11+, `jupyter_client`, `requests`, `pandas`, `pytest`, `streamlit` (demo only), Docker (production demo isolation only). LLM: Groq free-tier Llama-3.3-70B by default; Gemini-Flash for ablation.

**Spec reference:** [docs/superpowers/specs/2026-05-26-data-analysis-agent-design.md](../specs/2026-05-26-data-analysis-agent-design.md)

---

## File Structure (locked in before task decomposition)

```
agent/
  __init__.py             # package marker; exposes version
  llm_client.py           # provider-agnostic chat(messages) -> str; Groq + Gemini impls
  sandbox.py              # Sandbox class: wraps jupyter_client kernel; .execute() returns ExecutionResult
  orchestrator.py         # run(question, dataset_path) -> AgentResult; parses <code>/<answer>; retry logic
  trace.py                # StepRecord + Trace class; append-only JSON log per session
  cli.py                  # `python -m agent ask --data X "Q"`; thin wrapper around orchestrator
  eval/
    __init__.py
    run_dabench.py        # loads DABench tasks; runs agent on each; writes results JSON (resumable)
    results/              # gitignored; per-run JSON files

demo/
  app.py                  # Streamlit upload-and-chat UI; uses pre-vetted-datasets fallback by default
  datasets/               # 2-3 vetted CSVs used in fallback mode
  Dockerfile              # kernel sandbox for production demo (only used when arbitrary uploads enabled)

prompts/
  system.txt              # the agent system prompt (templated with {dataset_preview})

tests/
  conftest.py             # shared fixtures (tmp_path-based dataset, mocked LLM)
  test_sandbox.py
  test_llm_client.py
  test_trace.py
  test_orchestrator.py
  test_end_to_end.py      # full loop with scripted-mock LLM

pyproject.toml            # core deps + [project.optional-dependencies] demo = [streamlit]
README.md                 # how to install, run CLI, run eval, run demo, results table
.python-version           # 3.11
```

**Why this layout:**
- Each `agent/` module has one responsibility and is independently testable.
- `demo/` is outside `agent/` so `pip install agent` doesn't pull in Streamlit.
- `eval/results/` is the only directory that produces gitignored runtime output.
- Tests mirror module boundaries — easy to find the test file for a given module.

---

## Coding Conventions (apply throughout)

- **Type hints** on every public function and class.
- **No `print()` for control flow** — use `logging` for debug, return values for results.
- **Docstrings** only where the *why* is non-obvious (per project guidance: name things well and most docstrings are noise).
- **TDD**: every new module starts with a failing test.
- **Commit after each task** with conventional-commit-style messages (`feat:`, `test:`, `chore:`, `docs:`).

---

# Phase 0 — DABench Data Acquisition (do this BEFORE writing code)

DABench is the most likely place for an executor to get stuck. Resolve it first, in the open, before any code that references it.

## Task 0a: Clone the InfiAgent repo and locate DABench files

**Files:** none in this repo; populate `external/InfiAgent/` (gitignored).

- [ ] **Step 1: Clone InfiAgent**

```bash
mkdir -p external
git clone --depth 1 https://github.com/InfiAgent/InfiAgent.git external/InfiAgent
```

- [ ] **Step 2: Find the DABench task file and data directory**

```bash
find external/InfiAgent -name "*.jsonl" | head -20
find external/InfiAgent -name "*.csv" | head -10
```

Expected: at least one tasks `.jsonl` (likely `examples/DA-Agent/data/da-dev-questions.jsonl` or similar) and a directory of CSV tables. The exact paths may have changed since this plan was written — find them empirically.

- [ ] **Step 3: Record the absolute paths in a scratch file**

Create `external/PATHS.md` (gitignored) recording:
- `TASKS_JSONL=<absolute path to questions.jsonl>`
- `DATA_DIR=<absolute path to the CSV tables dir>`

The remaining tasks reference these as `$TASKS_JSONL` and `$DATA_DIR` — keep them in your shell environment for the rest of the plan.

- [ ] **Step 4: Add `external/` and `agent/eval/results/` to `.gitignore`**

The root `.gitignore` already excludes many things; ensure both are in it:

```bash
grep -q '^external/' .gitignore || echo 'external/' >> .gitignore
grep -q '^agent/eval/results/' .gitignore || echo 'agent/eval/results/' >> .gitignore
git add .gitignore && git commit -m "chore: gitignore external/ and eval results"
```

## Task 0b: Verify the task schema

The plan's code assumes specific field names (`id`, `question`, `data_file`, `expected_answer`). The real schema may differ — verify before writing the loader.

- [ ] **Step 1: Inspect one task**

```bash
head -1 "$TASKS_JSONL" | python -m json.tool
```

- [ ] **Step 2: Confirm or adjust field names**

Note the actual field names for: the unique task id, the question text, the dataset file reference, and the expected answer / answer format. If they differ from `id` / `question` / `data_file` / `expected_answer`, update Task 16's loader code accordingly.

- [ ] **Step 3: Verify the answer format**

DABench questions have **format constraints** (e.g., "answer with a single float to 2 decimal places"). The expected answer is structured. Skim 10 tasks to understand the format constraint vocabulary.

## Task 0c: Locate or write the official scorer

This is critical for the resume claim. A substring-match scorer (what Task 16 ships as a placeholder) does **not** match the published leaderboard.

- [ ] **Step 1: Search for the scoring code in the InfiAgent repo**

```bash
grep -ril "def.*eval\|def.*score" external/InfiAgent | head
```

- [ ] **Step 2: Note the official scorer's signature and import path**

Most likely something under `infiagent/eval/`. Record:
- Module path (e.g., `infiagent.eval.metrics`).
- Function signature.
- How it interprets the per-task format constraint.

- [ ] **Step 3: Decide one of two paths**

**Path A (preferred — honest):** plan to call the official scorer from `agent/eval/run_dabench.py` in Task 16, so the reported number is leaderboard-comparable. May require `pip install -e external/InfiAgent` or copying the scorer module.

**Path B (acceptable fallback):** keep the substring scorer but **rename** the metric throughout the README and case study from "DABench accuracy" to "approximate accuracy (substring match on DABench)" — never claim a leaderboard number. This is honest and easier; the resume sentence in spec §3 still works because it says "evaluated on InfiAgent-DABench" without claiming a leaderboard comparison.

Record which path you took. The README in Task 22 must match the path chosen.

- [ ] **Step 4: Commit the path decision**

Add a one-line note to `docs/superpowers/specs/2026-05-26-data-analysis-agent-design.md` at the bottom of §8 ("Selected scorer path: A" or "B") and commit.

---

# Phase 1 — Project Scaffolding

## Task 1: Initialize Python project structure

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `agent/__init__.py`
- Create: `agent/eval/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (empty for now)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "agent"
version = "0.1.0"
description = "Code-as-action data analysis agent."
requires-python = ">=3.11"
dependencies = [
    "jupyter_client>=8.6.0",
    "ipykernel>=6.29.0",
    "requests>=2.31.0",
    "pandas>=2.2.0",
    "matplotlib>=3.8.0",
]

[project.optional-dependencies]
demo = ["streamlit>=1.31.0"]
dev = ["pytest>=8.0.0", "pytest-mock>=3.12.0"]

[project.scripts]
agent = "agent.cli:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["agent*"]

[tool.setuptools.package-data]
"*" = ["prompts/*.txt"]

[tool.pytest.ini_options]
addopts = "-ra"
log_cli = false
```

- [ ] **Step 2: Write `.python-version`**

```
3.11
```

- [ ] **Step 3: Create empty `__init__.py` files**

`agent/__init__.py`:
```python
__version__ = "0.1.0"
```

`agent/eval/__init__.py`: empty file.

`tests/__init__.py`: empty file.

`tests/conftest.py`: empty file (will populate later).

- [ ] **Step 4: Create the virtual environment and install**

Run:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```
Expected: clean install, no errors.

- [ ] **Step 5: Verify pytest discovers nothing yet but runs**

Run: `pytest -v`
Expected: "no tests ran in X seconds" (exit code 5 is OK; means no tests collected). If pytest itself errors, the install is broken.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .python-version agent/ tests/
git commit -m "chore: scaffold Python package and dev environment"
```

---

# Phase 2 — Sandbox (foundation; everything depends on it)

## Task 2: Write failing test for sandbox basic execution

**Files:**
- Create: `tests/test_sandbox.py`
- Create: `agent/sandbox.py` (stub only)

- [ ] **Step 1: Write a stub `agent/sandbox.py` with just the types**

```python
from dataclasses import dataclass, field

@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exception: str | None = None  # full traceback if the cell raised
    figures: list[bytes] = field(default_factory=list)  # PNG bytes
    timed_out: bool = False

class Sandbox:
    def __init__(self, timeout_seconds: int = 30) -> None:
        raise NotImplementedError

    def execute(self, code: str) -> ExecutionResult:
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError
```

- [ ] **Step 2: Write the failing test**

`tests/test_sandbox.py`:
```python
import pytest
from agent.sandbox import Sandbox, ExecutionResult


def test_executes_simple_expression_and_captures_stdout():
    sb = Sandbox()
    try:
        result = sb.execute("print('hello')")
    finally:
        sb.close()
    assert isinstance(result, ExecutionResult)
    assert "hello" in result.stdout
    assert result.exception is None
    assert result.timed_out is False
```

- [ ] **Step 3: Run the test; verify it fails**

Run: `pytest tests/test_sandbox.py::test_executes_simple_expression_and_captures_stdout -v`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 4: Implement `Sandbox.__init__`, `.execute`, `.close`**

Replace the stub `Sandbox` with:
```python
import base64
import queue
import time
from jupyter_client.manager import start_new_kernel

class Sandbox:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout = timeout_seconds
        self._km, self._kc = start_new_kernel(kernel_name="python3")
        # Required: without this, the first execute() can race the
        # kernel's initial "status: busy" message and produce flaky output.
        self._kc.wait_for_ready(timeout=30)

    def execute(self, code: str) -> ExecutionResult:
        msg_id = self._kc.execute(code)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exception_text: str | None = None
        figures: list[bytes] = []
        timed_out = False

        # Single deadline — enforces total wall-clock per cell, not per message.
        deadline = time.monotonic() + self._timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                self._km.interrupt_kernel()
                self._drain_until_idle(msg_id)
                break
            try:
                msg = self._kc.get_iopub_msg(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            msg_type = msg["msg_type"]
            content = msg["content"]
            if msg_type == "stream":
                if content["name"] == "stdout":
                    stdout_parts.append(content["text"])
                else:
                    stderr_parts.append(content["text"])
            elif msg_type == "error":
                exception_text = "\n".join(content.get("traceback", []))
            elif msg_type in ("display_data", "execute_result"):
                data = content.get("data", {})
                if "image/png" in data:
                    figures.append(base64.b64decode(data["image/png"]))
            elif msg_type == "status" and content["execution_state"] == "idle":
                break

        return ExecutionResult(
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            exception=exception_text,
            figures=figures,
            timed_out=timed_out,
        )

    def _drain_until_idle(self, msg_id: str, hard_deadline: float = 5.0) -> None:
        """After interrupt, drain remaining messages so the next execute() doesn't see them."""
        end = time.monotonic() + hard_deadline
        while time.monotonic() < end:
            try:
                msg = self._kc.get_iopub_msg(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
                return

    def close(self) -> None:
        try:
            self._kc.stop_channels()
        finally:
            self._km.shutdown_kernel(now=True)
```

- [ ] **Step 5: Run the test; verify it passes**

Run: `pytest tests/test_sandbox.py::test_executes_simple_expression_and_captures_stdout -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/sandbox.py tests/test_sandbox.py
git commit -m "feat(sandbox): execute code in a Jupyter kernel and capture stdout"
```

## Task 3: Add tests + implementation for exception capture

**Files:**
- Modify: `tests/test_sandbox.py`

- [ ] **Step 1: Add failing test**

Append to `tests/test_sandbox.py`:
```python
def test_captures_exception_traceback():
    sb = Sandbox()
    try:
        result = sb.execute("1/0")
    finally:
        sb.close()
    assert result.exception is not None
    assert "ZeroDivisionError" in result.exception
```

- [ ] **Step 2: Run and verify it passes**

Run: `pytest tests/test_sandbox.py -v`
Expected: both tests PASS (the exception path is already implemented).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sandbox.py
git commit -m "test(sandbox): cover exception traceback capture"
```

## Task 4: Test timeout enforcement

**Files:**
- Modify: `tests/test_sandbox.py`

- [ ] **Step 1: Add failing test**

```python
def test_long_running_code_times_out():
    sb = Sandbox(timeout_seconds=2)
    try:
        result = sb.execute("import time; time.sleep(10); print('done')")
    finally:
        sb.close()
    assert result.timed_out is True
    assert "done" not in result.stdout
```

- [ ] **Step 2: Run and verify it passes (or fix sandbox)**

Run: `pytest tests/test_sandbox.py::test_long_running_code_times_out -v`
Expected: PASS. If FAIL, investigate the interrupt path in `Sandbox.execute`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sandbox.py
git commit -m "test(sandbox): verify timeout interrupts long-running cells"
```

## Task 5: Test figure capture

**Files:**
- Modify: `tests/test_sandbox.py`

- [ ] **Step 1: Add failing test**

```python
def test_captures_matplotlib_figure():
    sb = Sandbox()
    code = """
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
fig, ax = plt.subplots()
ax.plot([1, 2, 3], [4, 5, 6])
plt.show()
"""
    try:
        result = sb.execute(code)
    finally:
        sb.close()
    assert len(result.figures) >= 1
    assert result.figures[0].startswith(b"\x89PNG")
```

- [ ] **Step 2: Run and verify it passes**

Run: `pytest tests/test_sandbox.py::test_captures_matplotlib_figure -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_sandbox.py
git commit -m "test(sandbox): verify matplotlib figures are captured as PNG"
```

## Task 6: Sandbox state persistence between cells

**Files:**
- Modify: `tests/test_sandbox.py`

- [ ] **Step 1: Add failing test**

```python
def test_state_persists_across_executions():
    sb = Sandbox()
    try:
        sb.execute("x = 42")
        result = sb.execute("print(x)")
    finally:
        sb.close()
    assert "42" in result.stdout
```

- [ ] **Step 2: Run and verify it passes**

Run: `pytest tests/test_sandbox.py -v`
Expected: PASS (Jupyter kernels persist state by default).

- [ ] **Step 3: Commit**

```bash
git add tests/test_sandbox.py
git commit -m "test(sandbox): verify kernel state persists across cells"
```

---

# Phase 3 — LLM Client

## Task 7: Provider abstraction + Groq implementation

**Files:**
- Create: `agent/llm_client.py`
- Create: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing test (with mocked HTTP)**

`tests/test_llm_client.py`:
```python
from unittest.mock import patch, MagicMock
from agent.llm_client import GroqClient


def test_groq_client_sends_request_and_returns_content():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}]
    }
    with patch("agent.llm_client.requests.post", return_value=mock_response) as mock_post:
        client = GroqClient(api_key="test-key", model="llama-3.3-70b-versatile")
        out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "hello world"
    args, kwargs = mock_post.call_args
    assert "groq.com" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "llama-3.3-70b-versatile"
```

- [ ] **Step 2: Run; verify FAIL with import error**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL (module doesn't exist yet).

- [ ] **Step 3: Implement `agent/llm_client.py`**

```python
from typing import Protocol
import requests

class LLMClient(Protocol):
    def chat(self, messages: list[dict], **kwargs) -> str: ...


class GroqClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._model = model

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = {"model": self._model, "messages": messages, **kwargs}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self.URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Run and verify it passes**

Run: `pytest tests/test_llm_client.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm_client): add Groq client with mocked-HTTP tests"
```

## Task 8: Add backoff/retry for API failures

**Files:**
- Modify: `agent/llm_client.py`
- Modify: `tests/test_llm_client.py`

- [ ] **Step 1: Write failing test**

Append:
```python
import requests

def test_groq_client_retries_on_rate_limit():
    bad = MagicMock(status_code=429)
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert mock_sleep.call_count == 2  # two backoff sleeps
```

- [ ] **Step 2: Run; verify it FAILS**

Run: `pytest tests/test_llm_client.py::test_groq_client_retries_on_rate_limit -v`
Expected: FAIL.

- [ ] **Step 3: Add retry logic to `GroqClient.chat`**

In `agent/llm_client.py`:
```python
import time
# ... existing imports

class GroqClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 1.0

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._model = model

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = {"model": self._model, "messages": messages, **kwargs}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                resp = requests.post(self.URL, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except requests.HTTPError as exc:
                last_exc = exc
                status = getattr(exc.response, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < self.MAX_ATTEMPTS - 1:
                    time.sleep(self.BACKOFF_BASE_SECONDS * (2 ** attempt))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
```

- [ ] **Step 4: Run all llm_client tests**

Run: `pytest tests/test_llm_client.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/llm_client.py tests/test_llm_client.py
git commit -m "feat(llm_client): exponential-backoff retry on 429/5xx"
```

---

# Phase 4 — Trace Logging

## Task 9: StepRecord + Trace

**Files:**
- Create: `agent/trace.py`
- Create: `tests/test_trace.py`

- [ ] **Step 1: Write the failing test**

`tests/test_trace.py`:
```python
import json
from pathlib import Path
from agent.trace import Trace, StepRecord


def test_trace_records_steps_and_saves_json(tmp_path):
    trace = Trace(session_id="sess-1")
    trace.record(StepRecord(
        step=0,
        llm_messages=[{"role": "user", "content": "Q?"}],
        llm_response="<code>print(1)</code>",
        code="print(1)",
        stdout="1\n",
        stderr="",
        exception=None,
        timed_out=False,
    ))
    out = tmp_path / "trace.json"
    trace.save(out)

    data = json.loads(out.read_text())
    assert data["session_id"] == "sess-1"
    assert len(data["steps"]) == 1
    assert data["steps"][0]["code"] == "print(1)"
```

- [ ] **Step 2: Run; verify FAIL**

Run: `pytest tests/test_trace.py -v`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `agent/trace.py`**

```python
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class StepRecord:
    step: int
    llm_messages: list[dict]
    llm_response: str
    code: str | None
    stdout: str
    stderr: str
    exception: str | None
    timed_out: bool


@dataclass
class Trace:
    session_id: str
    steps: list[StepRecord] = field(default_factory=list)

    def record(self, step: StepRecord) -> None:
        self.steps.append(step)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({
            "session_id": self.session_id,
            "steps": [asdict(s) for s in self.steps],
        }, indent=2))
```

- [ ] **Step 4: Run; verify PASS**

Run: `pytest tests/test_trace.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/trace.py tests/test_trace.py
git commit -m "feat(trace): JSON trace log of agent steps"
```

---

# Phase 5 — Orchestrator (the agent loop)

## Task 10: Parser for `<code>` and `<answer>` blocks

**Files:**
- Create: `agent/orchestrator.py` (stub + parser)
- Create: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for parsing**

`tests/test_orchestrator.py`:
```python
from agent.orchestrator import parse_llm_response, ParsedResponse


def test_parses_code_block():
    out = parse_llm_response("Sure!\n<code>print(1)</code>\nDone.")
    assert out.code == "print(1)"
    assert out.answer is None


def test_parses_answer_block():
    out = parse_llm_response("<answer>The mean is 42.</answer>")
    assert out.answer == "The mean is 42."
    assert out.code is None


def test_parses_neither():
    out = parse_llm_response("I think the answer is 42.")
    assert out.answer is None
    assert out.code is None


def test_code_block_with_newlines_inside():
    out = parse_llm_response("<code>\nimport pandas as pd\ndf.head()\n</code>")
    assert "pandas" in out.code
    assert "df.head()" in out.code
```

- [ ] **Step 2: Write stub + parser**

`agent/orchestrator.py`:
```python
import re
from dataclasses import dataclass


@dataclass
class ParsedResponse:
    code: str | None
    answer: str | None


_CODE_RE = re.compile(r"<code>(.*?)</code>", re.DOTALL)
_ANSWER_RE = re.compile(r"<answer>(.*?)</answer>", re.DOTALL)


def parse_llm_response(text: str) -> ParsedResponse:
    code_m = _CODE_RE.search(text)
    ans_m = _ANSWER_RE.search(text)
    return ParsedResponse(
        code=code_m.group(1).strip() if code_m else None,
        answer=ans_m.group(1).strip() if ans_m else None,
    )
```

- [ ] **Step 3: Run tests; verify PASS**

Run: `pytest tests/test_orchestrator.py -v`
Expected: 4 PASS.

- [ ] **Step 4: Commit**

```bash
git add agent/orchestrator.py tests/test_orchestrator.py
git commit -m "feat(orchestrator): parse <code>/<answer> blocks from LLM output"
```

## Task 11: System prompt template

**Files:**
- Create: `prompts/system.txt`

Per Phase 0 findings, DABench's official scorer (`evaluate_responses` in `eval_closed_form.py`) extracts answers from the agent's response using the regex `@(\w+)\[(.*?)\]`. Tasks come with explicit `constraints` (natural-language) and `format` (the `@name[value]` template). The system prompt must:

1. Template `{constraints}` and `{format_constraint}` into the body.
2. Tell the model to emit final values as `@name[value]` tags inside `<answer>...</answer>`.

For CLI/ad-hoc use (no DABench task), the constraint sections can be empty strings — the model can still answer freely.

- [ ] **Step 1: Write the prompt**

`prompts/system.txt`:
```
You are a data analysis agent. You answer the user's question about a dataset by writing and executing Python code in a sandboxed Jupyter kernel.

The dataset is at: {dataset_path}
Preview:
{dataset_preview}

Each response must contain EXACTLY ONE of:
- A Python code block wrapped in <code>...</code> to execute next.
- A final answer wrapped in <answer>...</answer> when you have enough information.

Execution rules:
- Code blocks run in a persistent Jupyter kernel; variables persist across blocks.
- pandas, numpy, and matplotlib are available. Matplotlib figures are captured automatically when you call `plt.show()` — do NOT call `matplotlib.use(...)` (that suppresses the capture).
- Keep code blocks small and focused — one logical step per block.
- If a code block raises, you will see the traceback; fix and retry.
- The dataset is already at {dataset_path}; do not re-download or relocate it.

Answer rules:
- The question's constraints: {constraints}
- The required answer format: {format_constraint}

When emitting the final <answer>, include each required value as an "@name[value]" tag, exactly matching the names and types in the format constraint above. Example: <answer>@mean[42.50] @median[40.0]</answer>. If no format constraint was provided, write your answer as a brief natural-language sentence.
```

- [ ] **Step 2: Commit**

```bash
git add prompts/system.txt
git commit -m "feat(prompts): system prompt with @name[value] answer format"
```

## Task 12: Orchestrator main loop (with mocked LLM end-to-end test)

**Files:**
- Modify: `agent/orchestrator.py`
- Create: `tests/test_end_to_end.py`

- [ ] **Step 1: Write the failing end-to-end test**

`tests/test_end_to_end.py`:
```python
from pathlib import Path
import pandas as pd
from agent.orchestrator import run, AgentResult


class ScriptedLLM:
    """A mock LLM that returns a pre-scripted list of responses."""
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)

    def chat(self, messages, **_kwargs) -> str:
        if not self._responses:
            raise AssertionError("scripted LLM ran out of responses")
        return self._responses.pop(0)


def test_agent_answers_simple_question(tmp_path: Path):
    csv = tmp_path / "data.csv"
    pd.DataFrame({"x": [1, 2, 3, 4]}).to_csv(csv, index=False)

    llm = ScriptedLLM([
        "<code>import pandas as pd\ndf = pd.read_csv(r'" + str(csv) + "')\nprint(df['x'].mean())</code>",
        "<answer>The mean of x is 2.5.</answer>",
    ])
    # No constraints/format_constraint: CLI-style ad-hoc use.
    result = run(question="What is the mean of x?", dataset_path=str(csv), llm=llm)
    assert isinstance(result, AgentResult)
    assert result.success
    assert "2.5" in result.answer
    assert len(result.trace.steps) == 2
```

- [ ] **Step 2: Implement `run()` and `AgentResult`**

Append to `agent/orchestrator.py`:
```python
import logging
import uuid
from pathlib import Path
import pandas as pd

from agent.sandbox import Sandbox, ExecutionResult
from agent.trace import Trace, StepRecord

log = logging.getLogger(__name__)


@dataclass
class AgentResult:
    success: bool
    answer: str | None
    trace: Trace
    steps_taken: int
    failure_reason: str | None = None


MAX_STEPS = 10
MAX_RETRIES_PER_QUESTION = 3
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system.txt"


def _dataset_preview(path: str) -> str:
    try:
        df = pd.read_csv(path, nrows=5)
        return f"shape={df.shape}, dtypes={df.dtypes.to_dict()}\n{df.head().to_string()}"
    except Exception as exc:
        return f"(could not preview dataset: {exc})"


def _format_observation(result: ExecutionResult) -> str:
    parts = []
    if result.timed_out:
        parts.append("[timeout: cell exceeded the time limit]")
    if result.exception:
        parts.append(f"[exception]\n{result.exception}")
    if result.stdout:
        parts.append(f"[stdout]\n{result.stdout}")
    if result.stderr:
        parts.append(f"[stderr]\n{result.stderr}")
    if result.figures:
        parts.append(f"[generated {len(result.figures)} figure(s)]")
    return "\n".join(parts) or "[no output]"


def run(question: str, dataset_path: str, llm, *,
        retry_on_failure: bool = True,
        llm_kwargs: dict | None = None,
        constraints: str = "",
        format_constraint: str = "") -> AgentResult:
    """Run the agent loop against a dataset until <answer> or max steps.

    llm_kwargs is passed through to llm.chat() — eval runs should pass
    {"temperature": 0} for reproducibility.

    constraints + format_constraint come from a DABench task; empty
    strings are correct for ad-hoc CLI use.
    """
    session_id = str(uuid.uuid4())[:8]
    trace = Trace(session_id=session_id)
    sandbox = Sandbox()
    call_kwargs = llm_kwargs or {}

    system_prompt = PROMPT_PATH.read_text().format(
        dataset_path=dataset_path,
        dataset_preview=_dataset_preview(dataset_path),
        constraints=constraints or "(none)",
        format_constraint=format_constraint or "(none — answer in plain language)",
    )
    messages: list[dict] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question},
    ]

    retries_used = 0
    try:
        for step in range(MAX_STEPS):
            response = llm.chat(messages, **call_kwargs)
            parsed = parse_llm_response(response)

            if parsed.answer is not None:
                trace.record(StepRecord(
                    step=step, llm_messages=list(messages),
                    llm_response=response, code=None,
                    stdout="", stderr="", exception=None, timed_out=False,
                ))
                return AgentResult(True, parsed.answer, trace, step + 1)

            if parsed.code is None:
                messages.append({"role": "assistant", "content": response})
                messages.append({"role": "user", "content":
                    "Please respond with EITHER <code>...</code> OR <answer>...</answer>."})
                continue

            exec_result = sandbox.execute(parsed.code)
            observation = _format_observation(exec_result)

            trace.record(StepRecord(
                step=step, llm_messages=list(messages),
                llm_response=response, code=parsed.code,
                stdout=exec_result.stdout, stderr=exec_result.stderr,
                exception=exec_result.exception, timed_out=exec_result.timed_out,
            ))

            failed = exec_result.exception is not None or exec_result.timed_out
            if failed:
                if not retry_on_failure:
                    return AgentResult(
                        False, None, trace, step + 1,
                        failure_reason="cell failed (retry disabled)",
                    )
                # Check BEFORE incrementing so MAX_RETRIES_PER_QUESTION=3
                # really means "at most 3 retries, then stop."
                if retries_used >= MAX_RETRIES_PER_QUESTION:
                    return AgentResult(
                        False, None, trace, step + 1,
                        failure_reason="exceeded retry budget",
                    )
                retries_used += 1

            messages.append({"role": "assistant", "content": response})
            messages.append({"role": "user", "content": observation})

        return AgentResult(False, None, trace, MAX_STEPS,
                           failure_reason="max steps reached")
    finally:
        sandbox.close()
```

- [ ] **Step 3: Run the end-to-end test**

Run: `pytest tests/test_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/orchestrator.py tests/test_end_to_end.py
git commit -m "feat(orchestrator): agent loop with sandbox execution and trace"
```

## Task 12b: Unit-test `_format_observation` and `_dataset_preview`

These two helpers are on the hot path and silently swallow errors. Cover them.

**Files:**
- Modify: `tests/test_orchestrator.py`

- [ ] **Step 1: Add tests**

```python
from agent.orchestrator import _format_observation, _dataset_preview
from agent.sandbox import ExecutionResult


def test_format_observation_includes_all_present_fields():
    r = ExecutionResult(stdout="hi\n", stderr="warn\n",
                        exception="Traceback...", figures=[b"\x89PNG..."],
                        timed_out=False)
    out = _format_observation(r)
    assert "[stdout]" in out and "hi" in out
    assert "[stderr]" in out and "warn" in out
    assert "[exception]" in out
    assert "1 figure" in out


def test_format_observation_no_output_says_so():
    out = _format_observation(ExecutionResult())
    assert out == "[no output]"


def test_format_observation_timeout_flag(tmp_path):
    out = _format_observation(ExecutionResult(timed_out=True))
    assert "[timeout" in out


def test_dataset_preview_handles_missing_file(tmp_path):
    out = _dataset_preview(str(tmp_path / "nope.csv"))
    assert "could not preview" in out


def test_dataset_preview_returns_shape_and_head(tmp_path):
    import pandas as pd
    p = tmp_path / "d.csv"
    pd.DataFrame({"a": [1, 2, 3]}).to_csv(p, index=False)
    out = _dataset_preview(str(p))
    assert "(3, 1)" in out
```

- [ ] **Step 2: Run; verify PASS**

Run: `pytest tests/test_orchestrator.py -v`
Expected: all PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_orchestrator.py
git commit -m "test(orchestrator): cover format_observation and dataset_preview"
```

## Task 13: Test retry-off mode

**Files:**
- Modify: `tests/test_end_to_end.py`

- [ ] **Step 1: Add failing test**

```python
def test_retry_off_fails_immediately_on_exception(tmp_path: Path):
    csv = tmp_path / "data.csv"
    pd.DataFrame({"x": [1]}).to_csv(csv, index=False)
    llm = ScriptedLLM([
        "<code>raise ValueError('boom')</code>",
    ])
    result = run("Q?", str(csv), llm, retry_on_failure=False)
    assert result.success is False
    assert "retry disabled" in result.failure_reason
```

- [ ] **Step 2: Run, verify PASS**

Run: `pytest tests/test_end_to_end.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_end_to_end.py
git commit -m "test(orchestrator): retry-off ablation mode fails on first error"
```

---

# Phase 6 — CLI

## Task 14: `python -m agent ask`

**Files:**
- Create: `agent/cli.py`
- Modify: `agent/__init__.py` (add `__main__` support via cli)
- Create: `agent/__main__.py`

- [ ] **Step 1: Write `agent/cli.py`**

```python
import argparse
import os
import sys
from agent.orchestrator import run
from agent.llm_client import GroqClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent")
    sub = parser.add_subparsers(dest="cmd", required=True)

    ask = sub.add_parser("ask", help="ask the agent a question about a CSV")
    ask.add_argument("question", type=str)
    ask.add_argument("--data", required=True, help="path to CSV file")
    ask.add_argument("--model", default="llama-3.3-70b-versatile")
    ask.add_argument("--no-retry", action="store_true",
                     help="disable error retry (for ablation runs)")

    args = parser.parse_args(argv)

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("error: set GROQ_API_KEY", file=sys.stderr)
        return 2

    llm = GroqClient(api_key=api_key, model=args.model)
    result = run(args.question, args.data, llm, retry_on_failure=not args.no_retry)

    if result.success:
        print(result.answer)
        return 0
    print(f"agent failed: {result.failure_reason}", file=sys.stderr)
    return 1
```

- [ ] **Step 2: Write `agent/__main__.py`**

```python
import sys
from agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
```

- [ ] **Step 3: Smoke-test the CLI manually**

Run (requires real `GROQ_API_KEY`):
```bash
export GROQ_API_KEY=...   # get one from https://console.groq.com/keys

# Write a CSV with actual newlines (do not use `echo "...\n..."` — that
# writes literal backslash-n characters on most shells).
printf "x\n1\n2\n3\n4\n5\n" > /tmp/data.csv
head /tmp/data.csv   # verify it really has six lines

python -m agent ask --data /tmp/data.csv "What is the mean of x?"
```
Expected: prints a number close to 3.0.

If you don't have a Groq key yet, sign up — it's free — and rerun.

- [ ] **Step 4: Commit**

```bash
git add agent/cli.py agent/__main__.py
git commit -m "feat(cli): python -m agent ask --data X 'Q'"
```

---

# MVP GATE — first milestone

After Task 14 you have:
- A working CLI that answers questions about CSVs.
- A code-as-action loop with retry, traces, and tests for every module.

Next phases bring the eval harness, the demo, and the ablations needed for the resume claim.

---

# Phase 7 — Streamlit Demo (vetted-datasets mode)

## Task 15: Demo with pre-vetted datasets only

The public demo accepts dataset *choice* (not arbitrary upload) by default. This removes the RCE attack surface entirely (see spec §4a). Arbitrary upload is gated behind a `--allow-uploads` flag intended only for local use.

**Files:**
- Create: `demo/app.py`
- Create: `demo/datasets/` (download a few small public CSVs)

- [ ] **Step 1: Add 2–3 small CSVs to `demo/datasets/`**

Download or generate:
- `iris.csv` (sklearn's iris dataset exported to CSV)
- `titanic.csv` (a small public version)
- `tips.csv` (seaborn's tips dataset)

Commit them under `demo/datasets/`. Each should be < 500 KB.

- [ ] **Step 2: Write `demo/app.py`**

```python
import os
from pathlib import Path
import streamlit as st
from agent.orchestrator import run
from agent.llm_client import GroqClient

DATASETS_DIR = Path(__file__).parent / "datasets"

st.set_page_config(page_title="Data Analysis Agent", layout="wide")
st.title("Data Analysis Agent")
st.caption("Ask a question about one of the example datasets. The agent will write and run Python to answer.")

csvs = sorted(DATASETS_DIR.glob("*.csv"))
choice = st.selectbox("Dataset", [c.name for c in csvs])
question = st.text_input("Your question", "What is the average of the first numeric column?")
go = st.button("Ask")

if go and question:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        st.error("GROQ_API_KEY not set in this environment.")
    else:
        with st.spinner("Thinking..."):
            llm = GroqClient(api_key=api_key)
            result = run(question, str(DATASETS_DIR / choice), llm)
        if result.success:
            st.success(result.answer)
        else:
            st.error(f"Agent failed: {result.failure_reason}")
        with st.expander("Trace"):
            for step in result.trace.steps:
                st.code(step.code or "(no code — final answer step)", language="python")
                if step.stdout:
                    st.text(step.stdout)
                if step.exception:
                    st.error(step.exception)
```

- [ ] **Step 3: Smoke-test the demo locally**

Run:
```bash
pip install -e ".[demo]"
streamlit run demo/app.py
```
Expected: browser opens at `localhost:8501`; pick a dataset, ask a question, agent answers.

- [ ] **Step 4: Commit**

```bash
git add demo/
git commit -m "feat(demo): Streamlit UI with pre-vetted datasets"
```

## Task 15b: Deploy the demo (required by spec §13)

Spec §13 says the demo must be publicly accessible. Hugging Face Spaces is the simplest host that supports Streamlit and free `GROQ_API_KEY` secrets.

**Files:**
- Create: `demo/requirements.txt` (HF Spaces uses this; not pyproject.toml)
- Create: `demo/README.md` (HF Spaces config frontmatter goes here)

- [ ] **Step 1: Create a Hugging Face account and a new Space**

- Sign up at https://huggingface.co.
- Create a new Space: SDK = Streamlit, hardware = CPU basic (free).
- Note the Space's git URL.

- [ ] **Step 2: Write `demo/requirements.txt`**

```
streamlit>=1.31.0
jupyter_client>=8.6.0
ipykernel>=6.29.0
requests>=2.31.0
pandas>=2.2.0
matplotlib>=3.8.0
# Install the agent package itself from the repo. HF Spaces clones the repo,
# so a relative install works:
-e .
```

- [ ] **Step 3: Write `demo/README.md` with HF Spaces frontmatter**

```markdown
---
title: Data Analysis Agent
emoji: 📊
sdk: streamlit
sdk_version: 1.31.0
app_file: demo/app.py
pinned: false
---

Code-as-action data-analysis agent. See main repo for details.
```

- [ ] **Step 4: Add the `GROQ_API_KEY` secret in HF Spaces**

In the Space's Settings → Repository secrets, add `GROQ_API_KEY` with your key.

- [ ] **Step 5: Push to the Space**

```bash
git remote add hf <space-git-url>
git push hf main
```
Expected: HF Spaces builds and serves. URL is `https://huggingface.co/spaces/<user>/<space>`. Test the live demo end-to-end.

- [ ] **Step 6: Commit the deploy config**

```bash
git add demo/requirements.txt demo/README.md
git commit -m "feat(demo): Hugging Face Spaces deploy config"
```

---

# Phase 8 — Eval Harness (subset run for MVP gate)

## Task 16: DABench loader, scorer integration, runner

**Phase 0 findings that drive this task** (see `external/PATHS.md`):

- Tasks live in `da-dev-questions.jsonl`; answers in a SEPARATE `da-dev-labels.jsonl`. Join on `id`.
- Field name for the CSV is `file_name` (not `data_file`).
- Answer field on a label is `common_answers`: a `list[[name, value]]`.
- Constraint fields on a task: `constraints` (natural-language) and `format` (the `@name[value]` template). Both must be passed into the prompt.
- Total: 257 tasks. Headline metric: **ABQ** (Accuracy By Question — all sub-answers must match).
- Scorer: copy `external/InfiAgent/examples/DA-Agent/eval_closed_form.py` and `external/InfiAgent/examples/DA-Agent/utils/utils.py` into `agent/eval/scorers/infiagent/` (Path A2). Both are stdlib-only.

**Files:**
- Create: `agent/eval/scorers/__init__.py`
- Create: `agent/eval/scorers/infiagent/__init__.py`
- Create: `agent/eval/scorers/infiagent/eval_closed_form.py` (copied)
- Create: `agent/eval/scorers/infiagent/utils.py` (copied)
- Create: `agent/eval/run_dabench.py`

- [ ] **Step 1: Copy the official scorer (with attribution)**

```bash
mkdir -p agent/eval/scorers/infiagent
touch agent/eval/scorers/__init__.py
touch agent/eval/scorers/infiagent/__init__.py
cp external/InfiAgent/examples/DA-Agent/eval_closed_form.py agent/eval/scorers/infiagent/eval_closed_form.py
cp external/InfiAgent/examples/DA-Agent/utils/utils.py agent/eval/scorers/infiagent/utils.py
```

Prepend an attribution header to both files:
```python
# Copied from https://github.com/InfiAgent/InfiAgent
# (examples/DA-Agent/eval_closed_form.py and utils/utils.py)
# Used under the InfiAgent repo's license. Unmodified except for this header
# and any minimal import-path adjustments (e.g. `from .utils import ...`).
```

Adjust the import inside `eval_closed_form.py` so that `from utils.utils import read_jsonl` becomes `from .utils import read_jsonl`. Confirm no other imports break — both files should be stdlib-only.

Run a smoke check to verify the import works:
```bash
python3.11 -c "from agent.eval.scorers.infiagent.eval_closed_form import evaluate_responses; print('OK')"
```
Expected: `OK`.

- [ ] **Step 2: Write `agent/eval/run_dabench.py`**

```python
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

    # Resume support
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

        # Checkpoint after every task
        results_path.write_text(json.dumps({
            "run_id": results_path.stem,
            "results": results,
        }, indent=2))
        print(f"[{i+1}/{len(tasks)}] task {task['id']}: done")


def score_run(results_path: Path) -> dict:
    """Apply the official scorer to a completed run. Returns metric dict."""
    data = json.loads(results_path.read_text())
    # Build the inputs the official scorer expects.
    labels = [{"id": r["task_id"], "common_answers": r["common_answers"]}
              for r in data["results"] if "common_answers" in r]
    responses = [{"id": r["task_id"], "response": r["predicted_response"]}
                 for r in data["results"] if "predicted_response" in r]
    scored = evaluate_responses(labels, responses)
    # evaluate_responses returns per-task scores; aggregate to ABQ/PSAQ/UASQ
    # using whatever helper the upstream file exposes (verify by reading it).
    # If no aggregation helper exists, compute ABQ as:
    #   correct_tasks = sum(1 for s in scored if all sub-answers correct)
    #   ABQ = correct_tasks / len(scored)
    n = len(scored)
    abq_correct = sum(1 for s in scored if s.get("all_correct", False))
    return {"ABQ": abq_correct / n if n else 0.0,
            "n_tasks": n, "abq_correct": abq_correct}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", required=True, type=Path,
                        help="path to DABench da-dev-questions.jsonl")
    parser.add_argument("--labels", required=True, type=Path,
                        help="path to DABench da-dev-labels.jsonl")
    parser.add_argument("--data-dir", required=True, type=Path,
                        help="dir of CSVs (da-dev-tables/)")
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
```

> **Implementation note for the agent:** the exact field names returned by `evaluate_responses` (e.g., `all_correct`) need to be verified against the actual scorer source — read `agent/eval/scorers/infiagent/eval_closed_form.py` and adjust `score_run` if the return shape differs. The upstream scorer's primary loop computes per-sub-answer correctness; you may need to call a helper from the same file to get ABQ aggregation, or write the aggregation locally as shown.

- [ ] **Step 3: Verify it runs against a 5-task slice**

Use the paths recorded in `external/PATHS.md`:
```bash
source external/PATHS.md   # or copy/paste the values
python -m agent.eval.run_dabench \
  --questions "$TASKS_JSONL" \
  --labels "$LABELS_JSONL" \
  --data-dir "$DATA_DIR" \
  --subset 5 --run-id smoke-test
```
Expected: prints task-by-task progress; `agent/eval/results/smoke-test.json` exists; the final JSON metrics dict prints ABQ.

- [ ] **Step 4: Commit**

```bash
git add agent/eval/run_dabench.py
git commit -m "feat(eval): DABench runner with checkpoint/resume"
```

## Task 16b: Unit-test the eval loader and scorer integration

The scorer determines the resume number — it must be tested in isolation. Per Phase 0, the loader joins two JSONL files and the scorer is the official `evaluate_responses` (Path A2).

**Files:**
- Create: `tests/test_eval.py`

- [ ] **Step 1: Write tests**

```python
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
    assert tasks[0]["constraints"] == "c1"
    assert tasks[0]["format"] == "@x[float]"


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
```

- [ ] **Step 2: Run; verify PASS**

Run: `pytest tests/test_eval.py -v`

Note: `test_score_run_smoke` exercises the copied official scorer. If it fails, read `agent/eval/scorers/infiagent/eval_closed_form.py` and verify the expected response/label shape matches the test fixture.

- [ ] **Step 3: Commit**

```bash
git add tests/test_eval.py
git commit -m "test(eval): cover loader (join + subset + skip) and scorer integration"
```

## Task 17: First 80-task subset run

**Files:**
- Create: `agent/eval/results/subset-llama-retry.json` (output, gitignored)

- [ ] **Step 1: Run the 80-task subset with retry on**

```bash
python -m agent.eval.run_dabench \
  --questions "$TASKS_JSONL" \
  --labels "$LABELS_JSONL" \
  --data-dir "$DATA_DIR" \
  --subset 80 \
  --run-id subset-llama-retry
```
Expected: completes in ~30–60 minutes (rate-limited by Groq). Per-task progress prints; the final ABQ metric is printed at the end. The result JSON also has every task's full predicted response and common_answers, so you can re-score later without re-running.

- [ ] **Step 2: Re-score later by file**

```bash
python -m agent.eval.run_dabench --score-only \
  --questions "$TASKS_JSONL" --labels "$LABELS_JSONL" --data-dir "$DATA_DIR" \
  --run-id subset-llama-retry
```
Useful for debugging the scorer or iterating on aggregation.

- [ ] **Step 3: No commit (results are gitignored)** — but record the headline ABQ number, a few example successes, and a few example failures into a scratch note for the README.

---

# 🎯 MVP GATE REACHED

After Task 17 you have:
- A working CLI on real questions (Task 14).
- A **deployed, publicly accessible** Streamlit demo with vetted datasets (Tasks 15 + 15b).
- A real (or "leading-indicator", per the Phase 0c scorer decision) benchmark number on 80 DABench tasks (Task 17).
- A scorer whose behavior is unit-tested (Task 16b).

**The portfolio site is now unblocked.** A separate plan
(`docs/superpowers/plans/2026-05-26-portfolio-website.md`, to be written next)
covers the portfolio implementation. Continue with the post-MVP tasks below
to complete the resume claim.

---

# Phase 9 — Ablations & Full Run

## Task 18: Retry-off ablation on the subset

- [ ] **Step 1: Run the 80-task subset with retry off**

```bash
python -m agent.eval.run_dabench \
  --questions "$TASKS_JSONL" --labels "$LABELS_JSONL" --data-dir "$DATA_DIR" \
  --subset 80 --no-retry \
  --run-id subset-llama-noretry
```

- [ ] **Step 2: Compare ABQ with Task 17**

Record the delta (e.g., "Retry on: 42% ABQ; retry off: 31% ABQ; delta +11pp").

## Task 19: Add Gemini provider for two-model comparison

**Files:**
- Modify: `agent/llm_client.py`
- Modify: `tests/test_llm_client.py`
- Modify: `agent/eval/run_dabench.py`

Gemini's chat API differs from Groq's in two consequential ways:
1. There is no `system` role in `contents` — system instructions go in a separate top-level `system_instruction` field.
2. `contents` may not contain **consecutive same-role messages**; the API rejects them with 400.

The implementation must handle both.

- [ ] **Step 1: Write the failing tests first**

`tests/test_llm_client.py`:
```python
from agent.llm_client import GeminiClient

def test_gemini_lifts_system_message_into_system_instruction():
    with patch("agent.llm_client.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        }
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        out = client.chat([
            {"role": "system", "content": "you are an agent"},
            {"role": "user", "content": "hi"},
        ])
    assert out == "ok"
    sent = mock_post.call_args.kwargs["json"]
    assert sent["system_instruction"]["parts"][0]["text"] == "you are an agent"
    # No system role in `contents`
    assert all(c["role"] in ("user", "model") for c in sent["contents"])
    # No consecutive same-role messages
    roles = [c["role"] for c in sent["contents"]]
    assert all(a != b for a, b in zip(roles, roles[1:]))


def test_gemini_merges_consecutive_user_messages():
    with patch("agent.llm_client.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
        }
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        client.chat([
            {"role": "user", "content": "Q1"},
            {"role": "user", "content": "Q2"},  # observation message
        ])
    sent = mock_post.call_args.kwargs["json"]
    assert len(sent["contents"]) == 1
    assert "Q1" in sent["contents"][0]["parts"][0]["text"]
    assert "Q2" in sent["contents"][0]["parts"][0]["text"]
```

- [ ] **Step 2: Run the tests; verify FAIL**

Run: `pytest tests/test_llm_client.py::test_gemini_lifts_system_message_into_system_instruction -v`
Expected: FAIL (class doesn't exist yet).

- [ ] **Step 3: Add `GeminiClient` to `agent/llm_client.py`**

```python
class GeminiClient:
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    MAX_ATTEMPTS = 3
    BACKOFF_BASE_SECONDS = 1.0

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model = model

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> dict:
        """Returns {'system_instruction': ..., 'contents': [...]} with merged
        consecutive same-role turns; assistant messages map to 'model'."""
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        body = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] == "user" else "model"
            if body and body[-1]["role"] == role:
                body[-1]["parts"][0]["text"] += "\n\n" + m["content"]
            else:
                body.append({"role": role, "parts": [{"text": m["content"]}]})
        out: dict = {"contents": body}
        if system_parts:
            out["system_instruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return out

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = self._to_gemini_format(messages)
        # Pass through optional generation config (temperature, max_tokens)
        if "temperature" in kwargs or "max_tokens" in kwargs:
            gen_cfg = {}
            if "temperature" in kwargs:
                gen_cfg["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                gen_cfg["maxOutputTokens"] = kwargs["max_tokens"]
            payload["generationConfig"] = gen_cfg

        url = self.URL.format(model=self._model)
        last_exc: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                resp = requests.post(
                    url, params={"key": self._api_key},
                    json=payload, timeout=60,
                )
                resp.raise_for_status()
                return resp.json()["candidates"][0]["content"]["parts"][0]["text"]
            except requests.HTTPError as exc:
                last_exc = exc
                status = getattr(exc.response, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < self.MAX_ATTEMPTS - 1:
                    time.sleep(self.BACKOFF_BASE_SECONDS * (2 ** attempt))
                    continue
                raise
        assert last_exc is not None
        raise last_exc
```

- [ ] **Step 4: Add `--provider` flag to `agent/eval/run_dabench.py`**

In `main()` add:
```python
parser.add_argument("--provider", choices=["groq", "gemini"], default="groq")
```

In `run_eval()` accept a `provider` argument and switch clients:
```python
def _make_client(provider: str, model: str | None):
    if provider == "groq":
        return GroqClient(api_key=os.environ["GROQ_API_KEY"],
                          model=model or "llama-3.3-70b-versatile")
    if provider == "gemini":
        from agent.llm_client import GeminiClient
        return GeminiClient(api_key=os.environ["GEMINI_API_KEY"],
                            model=model or "gemini-2.0-flash")
    raise ValueError(f"unknown provider: {provider}")
```

**Update three places** so the new argument actually flows through:

1. Change `run_eval`'s signature to accept `provider: str = "groq"`.
2. Inside `run_eval`, replace the hardcoded `llm = GroqClient(...)` with `llm = _make_client(provider, model)`. Remove the now-unused `api_key = os.environ["GROQ_API_KEY"]` line above it.
3. In `main()`, pass `provider=args.provider` to the `run_eval(...)` call.

- [ ] **Step 5: Run tests; verify PASS**

Run: `pytest tests/test_llm_client.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/llm_client.py tests/test_llm_client.py agent/eval/run_dabench.py
git commit -m "feat(llm): Gemini provider with correct system+merge handling"
```

## Task 20: Gemini run on the subset

- [ ] **Step 1: Run**

```bash
python -m agent.eval.run_dabench \
  --questions "$TASKS_JSONL" --labels "$LABELS_JSONL" --data-dir "$DATA_DIR" \
  --subset 80 --provider gemini --run-id subset-gemini-retry
```

- [ ] **Step 2: Record the ABQ for the comparison table.**

## Task 21: Full 257-task run on the best configuration

- [ ] **Step 1: Pick the best (model, retry) combo from the subset runs.**

- [ ] **Step 2: Run the full benchmark**

```bash
python -m agent.eval.run_dabench \
  --questions "$TASKS_JSONL" --labels "$LABELS_JSONL" --data-dir "$DATA_DIR" \
  --run-id full-best
```
Note: this may take several hours and may exhaust the free tier — the resume support is built in, so re-run the same command after a wait if it stops mid-way.

- [ ] **Step 3: If the free tier blocks completion**, implement spec §8's `--allow-provider-fallback`:

This was deferred from the initial implementation. If you actually hit the rate-limit wall, add to `run_dabench.py`:
- A `--allow-provider-fallback` flag.
- When set, on a hard 429 after backoff exhaustion, swap the LLM client to the alternate provider for the remainder of the run.
- Record the provider per task in the result JSON (add a `"provider": "groq"|"gemini"` field to each task's result).
- The README's headline number must footnote any per-provider split.

If the free tier handles it without the swap, skip this step — but record in the README that the entire run was on a single provider.

- [ ] **Step 4: Record the headline number.**

---

# Phase 10 — Writeup & Hardening

## Task 22: README with results

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README** with sections:
  - **What this is** (one paragraph)
  - **Architecture** (small SVG or ascii diagram, link to spec)
  - **How to install** (`pip install -e ".[demo,dev]"`, set `GROQ_API_KEY`)
  - **How to use** (CLI example, demo command)
  - **Results table** with the headline number, the retry-on/off delta, and the two-model comparison
  - **Error analysis** — pick 3–5 representative failures from `eval/results/full-best.json` and write a short paragraph for each
  - **Design choices** including the LangChain-free note (per spec §13)
  - **Limitations & future work** including the sandbox-vs-vetted-datasets tradeoff

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with eval results and design notes"
```

## Task 23: Optional — Docker sandbox for arbitrary uploads

This is **post-MVP** and only needed if you decide to host the demo with arbitrary uploads enabled (e.g., a personal VPS). Hugging Face Spaces and Streamlit Community Cloud don't allow nested Docker, so vetted-datasets mode is the default deploy target.

**Files:**
- Create: `demo/Dockerfile`

Skip the details unless and until you decide to do this. See spec §4a for the requirements (no network, fs isolation, memory cap).

---

# Done criteria (per spec §13)

- [ ] Headline accuracy number on full DABench in README.
- [ ] Retry-on/off table in README.
- [ ] Two-model comparison table in README.
- [ ] Streamlit demo deployed and accessible.
- [ ] All unit tests pass via `pytest`.
- [ ] README mentions the LangChain-free choice.
- [ ] Portfolio site case-study page links back to this repo.
