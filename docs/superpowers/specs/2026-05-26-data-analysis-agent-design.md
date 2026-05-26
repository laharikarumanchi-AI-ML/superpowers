# Design: Data Analysis Agent

**Date:** 2026-05-26
**Owner:** Lahari Karumanchi
**Status:** Draft — pending user review

---

## 1. Goal

Build a code-as-action data-analysis agent: given a CSV (or tabular dataset) and a natural-language question, the agent autonomously writes and executes Python in a sandboxed Jupyter kernel until it produces an answer with supporting chart or table. Evaluate it on **InfiAgent-DABench** to obtain a credible benchmark number for the resume.

## 2. Why this project

Strengthens the Summer 2026 ML/SWE internship resume by:

- **Building on an existing strength** — extends the prior ReAct agent project with a more modern architecture (code-as-action) and rigorous evaluation, signaling progression.
- **Producing a concrete number** — a benchmark result on a published leaderboard is the kind of headline recruiters notice in a 10-second skim.
- **Filling a methodological gap** — none of the current resume projects include published-benchmark evaluation or model ablations. This one will.

## 3. Resume headline (target sentence)

> Built a code-as-action data-analysis agent (Python, sandboxed Jupyter execution); evaluated on InfiAgent-DABench (X% accuracy, N tasks), with ablations measuring the contribution of error-retry and comparing two open LLMs. Live Streamlit demo.

The `X%` is a placeholder. The success criterion is to **report an honest accuracy number and a measurable delta from the retry-off baseline**, not to hit a fixed threshold. Padding the number is a worse resume signal than reporting an unimpressive but honest result with thoughtful error analysis.

## 4. Scope

### In scope

- Code-as-action agent loop, written from scratch (no LangChain).
- Sandboxed Python execution via `jupyter_client`.
- Pluggable LLM backend; default to Groq's free Llama-3.3-70B.
- CLI entrypoint for benchmark runs and ad-hoc questions.
- Streamlit web demo where a user can upload a CSV and chat with the agent.
- Evaluation harness for InfiAgent-DABench (subset + full).
- Ablation runs: with/without error retry; Llama-3.3-70B vs Gemini-Flash on the eval subset.
- Trace logging (JSON) for every agent step.
- Unit tests for the sandbox and the orchestrator's parsing; one end-to-end test with mocked LLM.

### Out of scope (deliberate)

- Multi-agent (planner + critic + executor) architectures. Explored later if time permits.
- Fine-tuning. The contribution is the agent and evaluation, not model training.
- Authentication, user accounts, or persistence in the web demo. It is a demo.
- Production-grade observability (Prometheus, etc.). Trace JSON is sufficient.

## 4a. Threat model (public Streamlit demo)

The Streamlit demo accepts a CSV upload from any visitor and runs LLM-generated Python against it. Without isolation, that is arbitrary remote code execution on the host.

Mitigations for the public demo:

- **Process isolation:** the agent's Jupyter kernel runs inside a Docker container, separate from the Streamlit web process.
- **No network:** the kernel container runs with `--network=none`.
- **Filesystem isolation:** the only writable path is a per-session `/tmp/agent_session_<id>/` directory; the uploaded CSV is copied there and the kernel's working directory is set there.
- **Resource limits:** memory cap (1 GB), CPU share, hard wall-clock per cell (30 s).
- **Session lifetime:** kernel container destroyed on demo session end and after 10 minutes of inactivity.
- **Upload limit:** 10 MB max file size; CSV-only by extension and content sniff.

For **local CLI and eval runs**, the lighter `jupyter_client` direct kernel is fine — they execute trusted code on a trusted host. The Docker isolation path is the deployment target for `app.py` only.

If Docker is not available on the deployment platform (e.g., Hugging Face Spaces free tier), the demo falls back to refusing arbitrary uploads and instead offering 2–3 pre-vetted example datasets the user can choose from. This is an acceptable demo experience and removes the RCE surface entirely.

## 5. Architecture

```
   ┌────────────────────────────────────────────┐
   │           User (CLI / Streamlit)           │
   └──────────────────────┬─────────────────────┘
                          │ question + dataset
                          ▼
   ┌────────────────────────────────────────────┐
   │       Agent Loop (orchestrator.py)         │
   │                                            │
   │   parses <code>…</code> from LLM output,   │
   │   executes in sandbox, feeds result back,  │
   │   stops on <answer>…</answer> or max steps │
   └───┬─────────────┬──────────────┬───────────┘
       │             │              │
       ▼             ▼              ▼
   llm_client     sandbox          trace
   (Groq etc.)   (Jupyter)        (JSON log)
```

### Module responsibilities

| Module | Purpose | Public interface |
|---|---|---|
| `llm_client.py` | Provider-agnostic LLM wrapper. Default Groq; alternate Gemini for ablation. | `chat(messages: list[dict], **kwargs) -> str` |
| `sandbox.py` | One Jupyter kernel per session. Captures stdout, stderr, traceback, DataFrame head, generated figures (as base64 PNG). Enforces a 30-second per-cell timeout. | `Sandbox.execute(code: str) -> ExecutionResult`; `Sandbox.close()` |
| `orchestrator.py` | The agent loop. Constructs the prompt, parses `<code>` and `<answer>` tags from the LLM response, calls the sandbox, formats observations back into the conversation, retries on error, enforces a 10-step max. | `run(question: str, dataset_path: str) -> AgentResult` |
| `trace.py` | Append-only JSON log of every (prompt, llm response, parsed code, execution result) tuple. One file per session. | `Trace.record(step: StepRecord)`; `Trace.save(path)` |
| `eval/run_dabench.py` | Loads the InfiAgent-DABench task set, runs the agent on each task, scores with the benchmark's official metric, writes a summary JSON. | `python -m agent.eval.run_dabench --model groq --subset 80` |
| `cli.py` | One-shot interactive use. | `python -m agent ask --data foo.csv "What is the average value?"` |
| `app.py` | Streamlit upload-and-chat demo. | `streamlit run app.py` |

Each module has a single purpose and is independently testable. The agent loop never imports Streamlit, the CLI never imports the eval harness, etc.

## 6. The agent loop in detail

1. **Initial prompt:** system message describing the agent's role + tool (Python in a Jupyter kernel) + the dataset path and a quick preview (head + dtypes) + the user question + instructions to emit either a `<code>...</code>` block or a final `<answer>...</answer>`.
2. **Loop** (max 10 iterations):
   1. Call the LLM with the running conversation.
   2. Parse the response:
      - If it contains `<answer>...</answer>`, return that as the final answer.
      - If it contains `<code>...</code>`, extract and execute it in the sandbox.
      - If neither, send a corrective message ("Please respond with either a `<code>` block or a final `<answer>`") and continue.
   3. Format the execution result (stdout, stderr or traceback, DataFrame previews, figure references) and append it as the next user message.
   4. On exception: increment the per-question retry counter; if it exceeds 3, stop with a failure result.
3. If max steps are reached without a final answer, return `AgentResult(success=False, …)`.

## 7. Error handling

Definitions (used by §8 ablations):

- **"Retry"** in this spec means **automatic re-attempt of a failed code cell by feeding the failure back into the LLM prompt**. It covers both exceptions and timeouts. It does **not** cover format-correction messages for malformed LLM output (those are not retries — they are protocol enforcement and are always on).
- The **retry-off ablation** disables the exception/timeout retry path: a failed cell terminates that question with `success=False`. Malformed-output protocol enforcement remains on.

| Failure mode | Handling (retry-on) | Handling (retry-off ablation) |
|---|---|---|
| Cell exceeds 30 s timeout | Kill the cell, send a hint to the LLM: "Your last code timed out (>30 s). Try a more efficient approach." Counts against the 3-retry budget. | Question fails immediately. |
| Code raises an exception | Send the traceback back into the prompt. Up to 3 retries per question. | Question fails immediately. |
| LLM emits malformed output (no `<code>`/`<answer>` tags) | Send a corrective message asking for the expected format. **Not a retry — always on.** | Same. |
| LLM API failure (rate limit, network) | Exponential backoff with 3 attempts; otherwise fail the question. | Same. |
| Max steps reached | Return `success=False`, log the trace, continue. | Same. |

## 8. Evaluation plan

- **Iteration loop:** ~80-task subset of InfiAgent-DABench (stratified by question type so the subset is representative). Run in minutes, not hours. Enables fast prompt iteration.
- **Final number:** full 257-task DABench run with the best configuration.
- **Primary metric:** DABench top-level accuracy (correct answers / total). Sub-metrics per question type reported as a secondary breakdown table — not the headline number.
- **Ablations:**
  - **Retry on / retry off** on the subset — quantifies the value of self-correction. (Definition: see §7.)
  - **Groq Llama-3.3-70B vs Gemini-Flash** on the subset — a 2-row comparison table. This is a **two-model comparison**, not a comparison against a published baseline. The resume sentence (§3) is worded to reflect this.

All eval runs write to `eval/results/<run-id>.json` so they can be reproduced and inspected.

### Rate-limit fallback

Both Groq and Gemini free tiers have daily request caps. If a single full-DABench run hits the cap mid-way, the eval harness must (a) checkpoint after every task to `results/<run-id>.json`, (b) be resumable from the last completed task, and (c) automatically switch to the alternate provider only if the user passes `--allow-provider-fallback`. Provider switches mid-run must be recorded in the result file so the published number is honest about which tasks each model answered.

## 9. Testing

| Test | Purpose |
|---|---|
| `tests/test_sandbox.py` | Kernel lifecycle (start, execute, close), timeout enforcement, output capture (stdout, stderr, exceptions, figures). |
| `tests/test_orchestrator.py` | Parsing of well-formed and malformed LLM output (multiple code blocks, missing tags, nested tags), retry counter behavior, step-limit enforcement. |
| `tests/test_end_to_end.py` | One full agent run against a tiny CSV with a mocked LLM that returns a scripted sequence of `<code>` and `<answer>` responses. Verifies the assembled answer matches expectations. |

The benchmark itself acts as a large integration test.

## 10. Repository layout

```
agent/
  __init__.py
  llm_client.py
  sandbox.py
  orchestrator.py
  trace.py
  cli.py
  eval/
    __init__.py
    run_dabench.py
    results/        # gitignored
demo/
  app.py            # Streamlit demo — kept OUT of `agent/` so CLI/eval
                    # users don't need streamlit installed
  Dockerfile        # kernel-sandbox container (see §4a)
prompts/
  system.txt        # the agent system prompt (templated)
tests/
  test_sandbox.py
  test_orchestrator.py
  test_end_to_end.py
pyproject.toml      # core deps only; streamlit declared under an
                    # optional 'demo' extra
README.md
```

## 11. Dependencies

- `jupyter_client` — kernel management.
- `ipykernel` — the kernel process itself.
- `requests` — LLM API calls (intentionally avoiding heavy SDKs and LangChain).
- `pandas`, `numpy`, `matplotlib` — installed in the sandbox environment for the agent's use.
- `streamlit` — web demo only; declared as an optional `demo` extra in `pyproject.toml`, not pulled in by `pip install agent`.
- `pytest` — tests.

## 12. Open questions

- **Exact DABench subset selection** — stratify by difficulty? Random sample? Decide during plan-writing.
- **Streamlit hosting** — Hugging Face Spaces (free, simple) vs Streamlit Community Cloud. Decide later; both work.
- **Final eval-run cost** — Groq's free tier has per-day request limits. If we hit them on the full 257-task run, fall back to running it across two days or switching to Gemini-Flash mid-run.

## 13. Success criteria

The project is "done" when:

- The agent has an **honest accuracy number** on the full InfiAgent-DABench, written into the README, with a one-paragraph error analysis of failure modes.
- The retry-on-vs-off ablation table is in the README — even if the delta is small or negative, that is a legitimate and reportable result.
- The two-model comparison table (Llama-3.3-70B vs Gemini-Flash) is in the README.
- The Streamlit demo is publicly accessible with the §4a isolation measures in place (or operates in the "pre-vetted datasets only" fallback mode if Docker is unavailable on the host).
- All listed unit tests pass on `pytest`.
- The README explicitly mentions the LangChain-free design choice and why, so it does not read as ignorance of the framework landscape.
- The case-study page on the portfolio site references the result.

### MVP gate (for portfolio sequencing — see Portfolio §14)

The portfolio website may launch once the agent has reached **at minimum**: a working CLI run on a single example dataset, a benchmark number on the 80-task subset, and a working Streamlit demo. The full 257-task run, ablations, and writeup may follow after the portfolio launches.
