import json
from dataclasses import dataclass, field, asdict
from pathlib import Path


@dataclass
class StepRecord:
    step: int
    llm_messages: list[dict]
    llm_response: str
    code: str | None
    stdout: str
    stderr: str
    exception: str | None
    timed_out: bool


@dataclass
class Trace:
    session_id: str
    steps: list[StepRecord] = field(default_factory=list)

    def record(self, step: StepRecord) -> None:
        self.steps.append(step)

    def save(self, path: Path) -> None:
        path.write_text(json.dumps({
            "session_id": self.session_id,
            "steps": [asdict(s) for s in self.steps],
        }, indent=2))
