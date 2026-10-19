"""設定とUI構築のテスト。"""

import pytest

from ai_lie_game import config


def test_get_api_key_missing(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="APIキーが見つかりません"):
        config.get_api_key()


def test_get_api_key_placeholder_is_rejected(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-ここにあなたのAPIキーを書く")
    with pytest.raises(RuntimeError):
        config.get_api_key()


def test_get_api_key_ok(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-test")
    assert config.get_api_key() == "dummy-key-for-test"


def test_build_demo_does_not_need_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from ai_lie_game.ui import build_demo

    assert build_demo() is not None
