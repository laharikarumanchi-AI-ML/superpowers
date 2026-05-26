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
