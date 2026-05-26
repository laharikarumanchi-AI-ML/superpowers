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
