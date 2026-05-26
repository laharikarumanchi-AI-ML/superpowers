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


def test_retry_off_fails_immediately_on_exception(tmp_path: Path):
    csv = tmp_path / "data.csv"
    pd.DataFrame({"x": [1]}).to_csv(csv, index=False)
    llm = ScriptedLLM([
        "<code>raise ValueError('boom')</code>",
    ])
    result = run("Q?", str(csv), llm, retry_on_failure=False)
    assert result.success is False
    assert "retry disabled" in result.failure_reason
