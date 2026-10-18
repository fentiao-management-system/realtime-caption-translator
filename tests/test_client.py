import pytest

from app.ai import client as client_module
from app.ai.client import DeepSeekClient, DeepSeekError


class FakeResponse:
    def __init__(self, status_code: int = 200, content: str = "hello") -> None:
        self.status_code = status_code
        self.content = content
        self.text = "boom"

    def json(self) -> dict:
        if self.status_code != 200:
            raise AssertionError("不应解析错误响应")
        return {"choices": [{"message": {"content": self.content}}]}


def _fake_post(status_code: int = 200, content: str = "hello") -> None:
    def post(url, headers=None, json=None, timeout=None):
        return FakeResponse(status_code, content)

    client_module.requests.post = post


def test_translate_returns_content(monkeypatch) -> None:
    _fake_post(content="Hello")
    client = DeepSeekClient(api_key="sk-test")
    assert client.translate("你好") == "Hello"


def test_chat_builds_payload(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr(client_module.requests, "post", post)
    client = DeepSeekClient(api_key="sk-test")
    client.chat([{"role": "user", "content": "hi"}])
    assert captured["url"].endswith("/chat/completions")
    assert captured["headers"]["Authorization"] == "Bearer sk-test"
    assert captured["json"]["model"] == "deepseek-chat"


def test_api_error_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        client_module.requests,
        "post",
        lambda url, headers=None, json=None, timeout=None: FakeResponse(status_code=401, content=""),
    )
    client = DeepSeekClient(api_key="sk-test", max_retries=0)
    with pytest.raises(DeepSeekError, match="401"):
        client.chat([{"role": "user", "content": "hi"}])


def test_missing_key_raises() -> None:
    with pytest.raises(DeepSeekError, match="DEEPSEEK_API_KEY"):
        DeepSeekClient(api_key="")


def test_translate_with_context_and_glossary(monkeypatch) -> None:
    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def post(url, headers=None, json=None, timeout=None):
        captured["payload"] = json
        return FakeResponse()

    monkeypatch.setattr(client_module.requests, "post", post)
    client = DeepSeekClient(api_key="sk-test")
    client.translate(
        "项目进度不错",
        context=[("上次讨论了什么？", "What did we discuss last time?")],
        glossary={"项目进度": "project progress"},
    )
    system = captured["payload"]["messages"][0]["content"]
    assert "术语对照" in system
    assert "project progress" in system
    assert "前文" in system
    assert captured["payload"]["messages"][1]["content"] == "项目进度不错"
