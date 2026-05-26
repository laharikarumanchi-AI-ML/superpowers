from typing import Protocol
import requests


class LLMClient(Protocol):
    def chat(self, messages: list[dict], **kwargs) -> str: ...


class GroqClient:
    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile") -> None:
        self._api_key = api_key
        self._model = model

    def chat(self, messages: list[dict], **kwargs) -> str:
        payload = {"model": self._model, "messages": messages, **kwargs}
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self.URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
