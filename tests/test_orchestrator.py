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
