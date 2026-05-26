import base64
import queue
import time
from dataclasses import dataclass, field
from jupyter_client.manager import start_new_kernel


@dataclass
class ExecutionResult:
    stdout: str = ""
    stderr: str = ""
    exception: str | None = None  # full traceback if the cell raised
    figures: list[bytes] = field(default_factory=list)  # PNG bytes
    timed_out: bool = False


class Sandbox:
    def __init__(self, timeout_seconds: int = 30) -> None:
        self._timeout = timeout_seconds
        self._km, self._kc = start_new_kernel(kernel_name="python3")
        # Without wait_for_ready, the first execute() can race the
        # kernel's initial "status: busy" message and produce flaky output.
        self._kc.wait_for_ready(timeout=30)

    def execute(self, code: str) -> ExecutionResult:
        msg_id = self._kc.execute(code)
        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        exception_text: str | None = None
        figures: list[bytes] = []
        timed_out = False

        # Single deadline enforces total wall-clock per cell.
        deadline = time.monotonic() + self._timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                self._km.interrupt_kernel()
                self._drain_until_idle(msg_id)
                break
            try:
                msg = self._kc.get_iopub_msg(timeout=min(remaining, 1.0))
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            msg_type = msg["msg_type"]
            content = msg["content"]
            if msg_type == "stream":
                if content["name"] == "stdout":
                    stdout_parts.append(content["text"])
                else:
                    stderr_parts.append(content["text"])
            elif msg_type == "error":
                exception_text = "\n".join(content.get("traceback", []))
            elif msg_type in ("display_data", "execute_result"):
                data = content.get("data", {})
                if "image/png" in data:
                    figures.append(base64.b64decode(data["image/png"]))
            elif msg_type == "status" and content["execution_state"] == "idle":
                break

        return ExecutionResult(
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            exception=exception_text,
            figures=figures,
            timed_out=timed_out,
        )

    def _drain_until_idle(self, msg_id: str, hard_deadline: float = 5.0) -> None:
        """After interrupt, drain remaining messages so the next execute() doesn't see them."""
        end = time.monotonic() + hard_deadline
        while time.monotonic() < end:
            try:
                msg = self._kc.get_iopub_msg(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("parent_header", {}).get("msg_id") != msg_id:
                continue
            if msg["msg_type"] == "status" and msg["content"]["execution_state"] == "idle":
                return

    def close(self) -> None:
        try:
            self._kc.stop_channels()
        finally:
            self._km.shutdown_kernel(now=True)
