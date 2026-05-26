from typing import Protocol
import time
import requests


class LLMClient(Protocol):
    def chat(self, messages: list[dict], **kwargs) -> str: ...


class GroqClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"
    MAX_ATTEMPTS = 5
    BACKOFF_BASE_SECONDS = 2.0
    MAX_BACKOFF_SECONDS = 60.0

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._model = model

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = {"model": self._model, "messages": messages, **kwargs}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        last_exc: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                resp = requests.post(self.URL, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
            except requests.HTTPError as exc:
                last_exc = exc
                status = getattr(exc.response, "status_code", None)
                if status in (429, 500, 502, 503, 504) and attempt < self.MAX_ATTEMPTS - 1:
                    time.sleep(self._sleep_seconds(exc.response, attempt))
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    def _sleep_seconds(self, response, attempt: int) -> float:
        """Respect server's Retry-After if present; otherwise exponential backoff."""
        if response is not None:
            ra = response.headers.get("Retry-After") if hasattr(response, "headers") else None
            if ra:
                try:
                    return min(float(ra), self.MAX_BACKOFF_SECONDS)
                except (TypeError, ValueError):
                    pass
        return min(self.BACKOFF_BASE_SECONDS * (2 ** attempt), self.MAX_BACKOFF_SECONDS)
