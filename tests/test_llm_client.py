from unittest.mock import patch, MagicMock
from agent.llm_client import GroqClient


def test_groq_client_sends_request_and_returns_content():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "hello world"}}]
    }
    with patch("agent.llm_client.requests.post", return_value=mock_response) as mock_post:
        client = GroqClient(api_key="test-key", model="llama-3.3-70b-versatile")
        out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "hello world"
    args, kwargs = mock_post.call_args
    assert "groq.com" in args[0]
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"
    assert kwargs["json"]["model"] == "llama-3.3-70b-versatile"


import requests

def test_groq_client_retries_on_rate_limit():
    bad = MagicMock(status_code=429)
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert mock_sleep.call_count == 2  # two backoff sleeps
