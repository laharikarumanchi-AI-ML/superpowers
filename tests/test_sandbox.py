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


def test_captures_exception_traceback():
    sb = Sandbox()
    try:
        result = sb.execute("1/0")
    finally:
        sb.close()
    assert result.exception is not None
    assert "ZeroDivisionError" in result.exception


def test_long_running_code_times_out():
    sb = Sandbox(timeout_seconds=2)
    try:
        result = sb.execute("import time; time.sleep(10); print('done')")
    finally:
        sb.close()
    assert result.timed_out is True
    assert "done" not in result.stdout
