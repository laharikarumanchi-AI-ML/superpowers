# Data Analysis Agent

[![tests](https://github.com/laharikarumanchi-AI-ML/superpowers/actions/workflows/test.yml/badge.svg)](https://github.com/laharikarumanchi-AI-ML/superpowers/actions/workflows/test.yml)

A code-as-action AI agent that answers natural-language questions about CSV
datasets by writing and executing Python in a sandboxed Jupyter kernel.
Evaluated on [InfiAgent-DABench](https://github.com/InfiAgent/InfiAgent).

---

## Headline result

**Llama-3.3-70B (Groq), 9-task pilot of InfiAgent-DABench: 75% ABQ.**

The pilot is honest about its scope: 9 of 80 attempted tasks completed before
free-tier daily quotas ran out. The remaining tasks hit `429 Too Many Requests`
even with throttling — see [Limitations](#limitations) for what would scale
this. The agent loop itself works end-to-end (33 tests passing); the bottleneck
is API quota, not correctness.

| Configuration | Tasks scored | ABQ |
|---|---|---|
| Llama-3.3-70B + retry, 80-task subset attempt | 9 / 80 | **75%** |
| Llama-3.3-70B + retry-off ablation | (planned) | — |
| Gemini-2.0-Flash + retry, 50-task subset attempt | 0 / 50 (key issue + quota) | — |

---

## Quick start

```bash
# 1. Clone + install
git clone https://github.com/laharikarumanchi-AI-ML/superpowers.git
cd superpowers
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Add a free Groq key (https://console.groq.com/keys)
cat > .env <<'EOF'
GROQ_API_KEY=gsk_your_key_here
EOF

# 3. Ask the agent a question about any CSV
set -a && source .env && set +a
python -m agent ask --data demo/datasets/iris.csv \
  "What is the average sepal_length?"
# → "The average sepal_length is 5.84."

# 4. Run the eval (requires InfiAgent-DABench, see eval/ section below)
python -m agent.eval.run_dabench \
  --questions <path/to/da-dev-questions.jsonl> \
  --labels    <path/to/da-dev-labels.jsonl> \
  --data-dir  <path/to/da-dev-tables/> \
  --subset 80 --run-id subset-llama-retry
```

For the interactive web demo (Streamlit, local-only for now):

```bash
pip install -e ".[demo]"
streamlit run demo/app.py
```

---

## Architecture

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
   │   stops on <answer>…</answer> or 10 steps  │
   └───┬─────────────┬──────────────┬───────────┘
       │             │              │
       ▼             ▼              ▼
   llm_client     sandbox          trace
   (Groq /        (Jupyter)        (JSON log)
    Gemini)
```

The agent emits **code blocks**, not predefined tool calls. Every step looks
like:

```
<code>
import pandas as pd
df = pd.read_csv(path)
print(df.groupby('city')['fare'].mean())
</code>
```

The orchestrator extracts the block, executes it in a per-session Jupyter
kernel (`sandbox.py`), feeds stdout / stderr / tracebacks / DataFrame previews
back as the next observation, and repeats until the model emits `<answer>…</answer>`
or hits the 10-step ceiling.

Final answers carry `@name[value]` tags that the official InfiAgent scorer
extracts with `re.findall(r"@(\w+)\[(.*?)\]", response)`:

```
<answer>@mean_fare[34.65] @median_fare[28.50]</answer>
```

### Modules

| File | One-line responsibility |
|---|---|
| `agent/llm_client.py` | Provider-agnostic chat client. Groq + Gemini, with `Retry-After`-aware backoff and per-call throttling. |
| `agent/sandbox.py` | Wraps `jupyter_client`. Single deadline per cell, drains after interrupt, captures stdout, stderr, exceptions, and matplotlib figures. |
| `agent/orchestrator.py` | The agent loop. Parses `<code>` / `<answer>`, executes, formats observations, retries on cell failures (configurable). |
| `agent/trace.py` | JSON trace log of every (prompt, response, code, output) step. |
| `agent/cli.py` | `python -m agent ask --data X "Q"` |
| `agent/eval/run_dabench.py` | Loads DABench (joining questions + labels), runs the agent on each task, scores with the official `evaluate_responses`. |
| `agent/eval/scorers/infiagent/` | InfiAgent's `eval_closed_form.py` + `utils.py`, copied verbatim (with attribution) per [scorer-integration decision](docs/superpowers/specs/2026-05-26-data-analysis-agent-design.md#8-evaluation-plan). |
| `demo/app.py` | Streamlit upload-and-chat demo (vetted-datasets mode). |

---

## Key design choices

### Code-as-action, not ReAct tool-calling

Most "AI agent" projects use a ReAct loop with a predefined tool menu. This
agent generates Python directly. Trade-off: the LLM can write *any* pandas
chain (more expressive, better SOTA results) but you need a real sandbox to
execute it safely. The reward is a much richer space of solutions per task.

### Built without LangChain or other agent frameworks

The orchestrator is ~150 lines of straightforward Python. No `langchain`,
no `llamaindex`, no `crewai`. Frameworks make the surface area of the agent
loop opaque; writing it directly was the only way to understand (and debug)
behaviors like retry budgets, malformed-output recovery, and step limits.

This is a deliberate signal — "I want to understand my tools" — not a value
judgment of those frameworks.

### Real sandbox, not "sandbox"

A `subprocess.run('python …')` is not a sandbox; it's just a subprocess with
full host access. `agent/sandbox.py` does the unglamorous work:

- `wait_for_ready()` after kernel start so the first execute doesn't race
  the kernel's initial `status: busy` message.
- A single per-cell *deadline* (not per-message timeout) so the wall-clock
  budget is honest.
- After an interrupt fires, drain remaining messages so the next cell
  doesn't see ghost output.
- Capture stdout, stderr, exceptions (full traceback), and matplotlib
  figures (as PNG bytes).

The production-grade demo (per spec §4a) requires Docker isolation on top.
That's planned but not yet shipped — see [Limitations](#limitations).

### Official scorer, not a substring match

The first temptation when evaluating an LLM was to write
`predicted.lower() in expected.lower()` and call it 75% accuracy. That number
is meaningless — it doesn't match the DABench leaderboard. Instead, InfiAgent's
official `eval_closed_form.py` is copied into `agent/eval/scorers/infiagent/`
(with attribution) and used directly. The scorer extracts `@name[value]` tags,
matches names against `common_answers`, and uses strict `is_equal` with float
tolerance.

Trade-off: the official scorer is stricter, so the numbers are lower than a
naive scorer would report — but they are honest and leaderboard-comparable.

### Rate-limit handling as a first-class concern

Free-tier API quotas are not background noise — they shape what you can
evaluate. The Groq client respects `Retry-After` headers; the Gemini client
adds inter-call throttling tuned to its 15 RPM limit; the eval runner
checkpoints after every task so a mid-run quota crash is resumable. The
[blog post on this](https://laharikarumanchi.vercel.app/blog/building-da-agent)
goes deeper.

---

## Repo layout

```
agent/                    # The agent package
  llm_client.py
  sandbox.py
  orchestrator.py
  trace.py
  cli.py
  eval/
    run_dabench.py
    scorers/infiagent/    # Copied official scorer (with attribution)

demo/
  app.py                  # Streamlit UI
  datasets/               # Vetted demo CSVs (iris, tips, titanic)

prompts/
  system.txt              # The agent's system prompt

tests/                    # pytest suite (33 tests, all green)

docs/superpowers/
  specs/                  # Design docs (spec for agent + spec for portfolio)
  plans/                  # Implementation plans (TDD-style task breakdowns)
```

External dependencies (cloned, not committed):

- `external/InfiAgent/` — the upstream repo containing DABench. Gitignored;
  the scorer files are copied into `agent/eval/scorers/infiagent/` with
  attribution.

---

## Testing

```bash
pytest -v
```

33 tests across 6 files: sandbox lifecycle/timeout/figure-capture/state
persistence, LLM client retry/backoff/key-scrub/throttle, trace JSON
serialization, orchestrator parsing + helpers, end-to-end with a scripted
mock LLM, and eval loader/scorer integration.

CI runs this same command on every push and PR via GitHub Actions
([`.github/workflows/test.yml`](.github/workflows/test.yml)).

---

## Limitations

- **Quota-bounded headline**. The 75% ABQ figure is on 9 of 80 attempted
  tasks; the rest hit free-tier limits. Scaling to the full 257-task DABench
  requires a paid tier (~$5 on Groq Dev or pay-per-use on Gemini) or a slow
  multi-day run. The code is ready; the budget isn't.
- **Local-only public demo**. The Streamlit app supports CSV uploads, but
  shipping that publicly is RCE-on-a-platter without sandboxing. The
  production-deploy path uses Docker isolation per
  [spec §4a](docs/superpowers/specs/2026-05-26-data-analysis-agent-design.md#4a-threat-model-public-streamlit-demo);
  the vetted-datasets fallback ships safely but isn't deployed yet.
- **No fine-tuning**. The agent's quality is bounded by the base model's
  reasoning. A LoRA-fine-tuned Llama on DABench format constraints would
  likely jump several points; it's deliberately out of scope for this
  project (which is about agent design + evaluation, not training).
- **Single-model per run**. The eval doesn't yet fall back across providers
  mid-run when one quota exhausts; this is documented in the plan as a
  deferred improvement.

---

## What's next

In priority order:

1. **Full 257-task DABench run** once a paid tier is in place.
2. **Retry-on / retry-off ablation** on the full subset to quantify
   self-correction value.
3. **Two-model comparison table** (Llama vs Gemini) with honest
   per-provider footnotes.
4. **Deploy the Streamlit demo** to Hugging Face Spaces (vetted-datasets mode).
5. **Error analysis** — categorize the failures from the full run into
   recoverable / non-recoverable / out-of-scope.
6. **A small LoRA experiment** on DABench-format-constrained tasks.

---

## What I'd do differently
<!-- Lahari: rewrite this in your voice. The honest reflection here is the
single most useful section for a recruiter. Suggested raw material:

- Treat free-tier rate limits as a first-class design constraint, not a
  bug to retry around. Would have changed the scope from "80-task subset"
  to "20-task subset with proper throttling" on day one.
- The Phase-0 discovery work (finding that DABench uses a separate labels
  file, not inline answers; that the official scorer uses `@name[value]`
  regex extraction) saved hours later. I'd do this discovery for *any*
  benchmark integration, not just hope the schema is what I assume.
- The Gemini API leaking keys via `?key=...` URL parameter is a real-world
  example of why "shift left on security" matters for student projects too.
- I'd write the agent loop, then run a single end-to-end smoke test
  against the real API, *before* writing the eval harness. Some of the
  bugs we caught (matplotlib backend, retry budget off-by-one, prompt
  format) would have surfaced cheaper.

Edit this freely.
-->

---

## About me
<!-- Lahari: short bio paragraph here. The portfolio's About page has the
longer version; this is just the project's footer. Suggested template:

> Third-year CS @ CVR College of Engineering, Hyderabad. Building
> code-as-action agents, RAG systems, and the occasional opinion piece on
> ML evaluation. Recruiting for Summer 2026 ML/SWE internships.
> Site: <https://laharikarumanchi.vercel.app>
-->

---

## Acknowledgments

- **[InfiAgent-DABench](https://github.com/InfiAgent/InfiAgent)** for the
  benchmark and the official scorer (used under their license; the relevant
  files in `agent/eval/scorers/infiagent/` carry attribution headers).
- **Groq** and **Google AI Studio** for the free LLM tiers that made
  iteration possible.
- This project was paired with **Claude Code** through an end-to-end
  spec → plan → review → implement → reflect workflow. The implementation
  decisions, design choices, and "what I'd do differently" reflections are
  mine; the typing fingers were partly silicon.
