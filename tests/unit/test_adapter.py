import httpx
import pytest

from local_subagent.runtime.adapter import LocalModelAdapter


def test_adapter_posts_openai_compatible_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("Authorization")
        captured["payload"] = request.read().decode("utf-8")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"message":"Need shell output.",'
                                '"tool_requests":[{"name":"shell","arguments":{"cmd":"pwd"}}],'
                                '"done":false,'
                                '"confidence":0.4,'
                                '"assumptions":["pwd is available."]}'
                            )
                        }
                    }
                ]
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LocalModelAdapter(
        base_url="http://127.0.0.1:11434/v1",
        api_key="secret",
        model_name="qwen-test",
        temperature=0.3,
        max_tokens=512,
        http_client=client,
    )

    response = adapter.complete(
        [{"role": "user", "content": "Inspect the current directory."}]
    )

    assert captured["method"] == "POST"
    assert captured["url"] == "http://127.0.0.1:11434/v1/chat/completions"
    assert captured["authorization"] == "Bearer secret"
    assert '"model":"qwen-test"' in captured["payload"]
    assert '"temperature":0.3' in captured["payload"]
    assert '"max_tokens":512' in captured["payload"]
    assert '"response_format":{"type":"json_object"}' in captured["payload"]
    assert '"role":"system"' in captured["payload"]
    assert '"role":"user"' in captured["payload"]
    assert response.tool_requests[0].name == "shell"
    assert response.tool_requests[0].arguments == {"cmd": "pwd"}
    assert response.done is False


def test_adapter_rejects_non_json_model_content():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not json"}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = LocalModelAdapter(
        base_url="http://127.0.0.1:11434/v1",
        api_key="secret",
        model_name="qwen-test",
        http_client=client,
    )

    with pytest.raises(ValueError, match="JSON"):
        adapter.complete([{"role": "user", "content": "Hi"}])
