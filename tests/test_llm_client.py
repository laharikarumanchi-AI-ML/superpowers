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
    bad.headers = {}  # no Retry-After
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    assert mock_sleep.call_count == 2  # two backoff sleeps


def test_groq_client_respects_retry_after_header():
    """When Groq returns a Retry-After header, sleep for that many seconds."""
    bad = MagicMock(status_code=429)
    bad.headers = {"Retry-After": "7"}
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            out = client.chat([{"role": "user", "content": "hi"}])
    assert out == "ok"
    mock_sleep.assert_called_once_with(7.0)


def test_groq_client_caps_retry_after_at_max_backoff():
    """A pathologically large Retry-After is capped at MAX_BACKOFF_SECONDS."""
    bad = MagicMock(status_code=429)
    bad.headers = {"Retry-After": "9999"}  # an hour-ish — cap it
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            client.chat([{"role": "user", "content": "hi"}])
    mock_sleep.assert_called_once_with(GroqClient.MAX_BACKOFF_SECONDS)


def test_groq_client_attempts_up_to_max_then_raises():
    """5 attempts total; 4 sleeps; then raise."""
    bad = MagicMock(status_code=429)
    bad.headers = {}
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    with patch("agent.llm_client.requests.post", return_value=bad):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GroqClient(api_key="k", model="m")
            try:
                client.chat([{"role": "user", "content": "hi"}])
                assert False, "expected HTTPError to propagate"
            except requests.HTTPError:
                pass
    assert mock_sleep.call_count == GroqClient.MAX_ATTEMPTS - 1  # 4 sleeps between 5 attempts


# ---- Gemini client tests ----
from agent.llm_client import GeminiClient


def test_gemini_lifts_system_message_into_system_instruction():
    """System role must go in top-level system_instruction, not in contents."""
    good = MagicMock(status_code=200)
    good.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}]
    }
    with patch("agent.llm_client.requests.post", return_value=good) as mock_post:
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        out = client.chat([
            {"role": "system", "content": "you are an agent"},
            {"role": "user", "content": "hi"},
        ])
    assert out == "ok"
    sent = mock_post.call_args.kwargs["json"]
    assert sent["system_instruction"]["parts"][0]["text"] == "you are an agent"
    # No system role in contents
    assert all(c["role"] in ("user", "model") for c in sent["contents"])
    # No consecutive same-role messages
    roles = [c["role"] for c in sent["contents"]]
    assert all(a != b for a, b in zip(roles, roles[1:]))


def test_gemini_merges_consecutive_user_messages():
    """Gemini API rejects consecutive same-role turns; must merge."""
    good = MagicMock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    with patch("agent.llm_client.requests.post", return_value=good) as mock_post:
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        client.chat([
            {"role": "user", "content": "Q1"},
            {"role": "user", "content": "Q2"},
        ])
    sent = mock_post.call_args.kwargs["json"]
    assert len(sent["contents"]) == 1
    text = sent["contents"][0]["parts"][0]["text"]
    assert "Q1" in text and "Q2" in text


def test_gemini_assistant_role_maps_to_model():
    good = MagicMock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    with patch("agent.llm_client.requests.post", return_value=good) as mock_post:
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        client.chat([
            {"role": "user", "content": "Q1"},
            {"role": "assistant", "content": "A1"},
            {"role": "user", "content": "Q2"},
        ])
    sent = mock_post.call_args.kwargs["json"]
    roles = [c["role"] for c in sent["contents"]]
    assert roles == ["user", "model", "user"]


def test_gemini_passes_temperature_through_generation_config():
    good = MagicMock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    with patch("agent.llm_client.requests.post", return_value=good) as mock_post:
        client = GeminiClient(api_key="k", model="gemini-2.0-flash")
        client.chat([{"role": "user", "content": "hi"}], temperature=0)
    sent = mock_post.call_args.kwargs["json"]
    assert sent["generationConfig"]["temperature"] == 0


def test_gemini_respects_retry_after_header():
    bad = MagicMock(status_code=429)
    bad.headers = {"Retry-After": "5"}
    bad.raise_for_status.side_effect = requests.HTTPError(response=bad)
    good = MagicMock(status_code=200)
    good.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
    with patch("agent.llm_client.requests.post", side_effect=[bad, good]):
        with patch("agent.llm_client.time.sleep") as mock_sleep:
            client = GeminiClient(api_key="k", model="gemini-2.0-flash")
            client.chat([{"role": "user", "content": "hi"}])
    mock_sleep.assert_called_once_with(5.0)
