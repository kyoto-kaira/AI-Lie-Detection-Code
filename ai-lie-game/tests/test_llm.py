"""AIに送る内容のテスト（APIは呼ばない。OpenAIのクライアントを差し替える）。"""

from types import SimpleNamespace

from ai_lie_game import config, llm


class FakeClient:
    def __init__(self):
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    def create(self, **kwargs):
        self.requests.append(kwargs)
        message = SimpleNamespace(content='{"a": 1}')
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


def run(monkeypatch, effort):
    fake = FakeClient()
    monkeypatch.setattr(llm, "get_client", lambda: fake)
    monkeypatch.setattr(config, "REASONING_EFFORT", effort)
    assert llm.call_llm("system", "user") == {"a": 1}
    return fake.requests[0]


def test_reasoning_effort_not_sent_by_default(monkeypatch):
    request = run(monkeypatch, "")
    assert "reasoning_effort" not in request  # gpt-4o-mini などでもエラーにならない
    assert request["max_completion_tokens"] == config.MAX_TOKENS


def test_reasoning_effort_sent_when_set(monkeypatch):
    request = run(monkeypatch, "none")
    assert request["reasoning_effort"] == "none"
