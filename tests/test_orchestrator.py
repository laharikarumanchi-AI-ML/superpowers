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
