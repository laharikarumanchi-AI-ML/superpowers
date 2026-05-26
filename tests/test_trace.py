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
