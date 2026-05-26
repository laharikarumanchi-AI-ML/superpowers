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

> Built a code-as-action data-analysis agent (Python, sandboxed Jupyter); achieved X% on InfiAgent-DABench, ablated against Llama-3.3-70B baseline with retry/no-retry comparison. Live Streamlit demo.

The `X%` is a placeholder — we set the bar to "beat the published Llama-3.3-70B zero-shot baseline by ≥5 points" as a stretch but tractable success criterion.

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

| Failure mode | Handling |
|---|---|
| Cell exceeds 30s timeout | Kill the cell, send a hint to the LLM: "Your last code timed out (>30s). Try a more efficient approach." Counts against the 3-retry budget. |
| Code raises an exception | Send the traceback back into the prompt. Up to 3 retries per question. |
| LLM emits malformed output (no `<code>`/`<answer>` tags) | Send a corrective message asking for the expected format. Does not count as a retry. |
| LLM API failure (rate limit, network) | Exponential backoff with 3 attempts; otherwise fail the question. |
| Max steps reached | Return `success=False`, log the trace, continue to the next benchmark task. |

## 8. Evaluation plan

- **Iteration loop:** ~80-task subset of InfiAgent-DABench. Run in minutes, not hours. Enables fast prompt iteration.
- **Final number:** full 257-task DABench run with the best configuration.
- **Ablations:**
  - **Retry on / retry off** on the subset — quantifies the value of self-correction.
  - **Groq Llama-3.3-70B vs Gemini-Flash** on the subset — produces a 2-row comparison table.

All eval runs write to `eval/results/<run-id>.json` so they can be reproduced and inspected.

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
  app.py
  eval/
    __init__.py
    run_dabench.py
    results/        # gitignored
prompts/
  system.txt        # the agent system prompt (templated)
tests/
  test_sandbox.py
  test_orchestrator.py
  test_end_to_end.py
pyproject.toml
README.md
```

## 11. Dependencies

- `jupyter_client` — kernel management.
- `ipykernel` — the kernel process itself.
- `requests` — LLM API calls (intentionally avoiding heavy SDKs and LangChain).
- `pandas`, `numpy`, `matplotlib` — installed in the sandbox environment for the agent's use.
- `streamlit` — web demo only.
- `pytest` — tests.

## 12. Open questions

- **Exact DABench subset selection** — stratify by difficulty? Random sample? Decide during plan-writing.
- **Streamlit hosting** — Hugging Face Spaces (free, simple) vs Streamlit Community Cloud. Decide later; both work.
- **Final eval-run cost** — Groq's free tier has per-day request limits. If we hit them on the full 257-task run, fall back to running it across two days or switching to Gemini-Flash mid-run.

## 13. Success criteria

The project is "done" when:

- The agent achieves a benchmark number on the full InfiAgent-DABench, written into the README.
- The retry-on-vs-off ablation produces a measurable difference, written into the README as a table.
- The Streamlit demo is publicly accessible and lets a visitor upload a CSV and ask a question end-to-end.
- All listed unit tests pass on `pytest`.
- The case-study page on the portfolio site references the result.
