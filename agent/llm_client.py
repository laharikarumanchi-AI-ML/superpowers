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


class GeminiClient:
    """Google Gemini chat client. Free tier has much higher TPM than Groq's
    free Llama tier, which matters for sequential agent runs."""
    URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    MAX_ATTEMPTS = 5
    BACKOFF_BASE_SECONDS = 2.0
    MAX_BACKOFF_SECONDS = 60.0

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash") -> None:
        self._api_key = api_key
        self._model = model

    @staticmethod
    def _to_gemini_format(messages: list[dict]) -> dict:
        """Convert OpenAI-style chat messages to Gemini's API shape:
        - system messages lift into top-level `system_instruction`
        - assistant role -> 'model'; user role -> 'user'
        - consecutive same-role turns are merged (Gemini rejects them otherwise)
        """
        system_parts = [m["content"] for m in messages if m["role"] == "system"]
        body: list[dict] = []
        for m in messages:
            if m["role"] == "system":
                continue
            role = "user" if m["role"] == "user" else "model"
            if body and body[-1]["role"] == role:
                body[-1]["parts"][0]["text"] += "\n\n" + m["content"]
            else:
                body.append({"role": role, "parts": [{"text": m["content"]}]})
        out: dict = {"contents": body}
        if system_parts:
            out["system_instruction"] = {
                "parts": [{"text": "\n\n".join(system_parts)}]
            }
        return out

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = self._to_gemini_format(messages)
        gen_cfg: dict = {}
        if "temperature" in kwargs:
            gen_cfg["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            gen_cfg["maxOutputTokens"] = kwargs["max_tokens"]
        if gen_cfg:
            payload["generationConfig"] = gen_cfg

        url = self.URL.format(model=self._model)
        last_exc: Exception | None = None
        for attempt in range(self.MAX_ATTEMPTS):
            try:
                resp = requests.post(url, params={"key": self._api_key},
                                     json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
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
        if response is not None:
            ra = response.headers.get("Retry-After") if hasattr(response, "headers") else None
            if ra:
                try:
                    return min(float(ra), self.MAX_BACKOFF_SECONDS)
                except (TypeError, ValueError):
                    pass
        return min(self.BACKOFF_BASE_SECONDS * (2 ** attempt), self.MAX_BACKOFF_SECONDS)
