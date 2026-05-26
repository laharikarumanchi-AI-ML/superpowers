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
