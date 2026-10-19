"""ゲームBのテスト（APIは呼ばない）。"""

import pytest

from ai_lie_game import config, game_b


def test_precheck_ok_and_normalizes_fullwidth():
    ok, _, cleaned = game_b.precheck_story("　きのう、カレーを３ばいおかわりした　")
    assert ok
    assert cleaned == "きのう、カレーを3ばいおかわりした"


def test_precheck_too_short():
    ok, message, _ = game_b.precheck_story("あ")
    assert not ok
    assert "みじかすぎる" in message


def test_precheck_too_long():
    ok, message, _ = game_b.precheck_story("あ" * (config.STORY_MAX_LEN + 1))
    assert not ok
    assert "ながすぎる" in message


@pytest.mark.parametrize(
    "story",
    [
        "でんわばんごうは090-1234-5678です",
        "メールは taro@example.com です",
        "うちの郵便番号は 606-8501 だよ",
    ],
)
def test_precheck_blocks_personal_info(story):
    ok, _, _ = game_b.precheck_story(story)
    assert not ok


def test_validate_judge_normalizes():
    result = game_b.validate_judge({"is_appropriate": "true", "guess": "LIE ", "reason": " りゆう "})
    assert result == {"is_appropriate": True, "guess": "lie", "reason": "りゆう"}


def test_validate_judge_rejects_bad_guess():
    with pytest.raises(ValueError):
        game_b.validate_judge({"is_appropriate": True, "guess": "maybe", "reason": "x"})


def test_check_result_player_wins_when_ai_wrong():
    judge = {"guess": "true", "reason": "r"}
    assert game_b.check_result(judge, "lie")["player_wins"] is True
    assert game_b.check_result(judge, "true")["player_wins"] is False


def test_play_b_updates_state(monkeypatch):
    monkeypatch.setattr(
        game_b,
        "judge_story",
        lambda story: {"is_appropriate": True, "guess": "true", "reason": "りゆう"},
    )
    state, result = game_b.play_b(None, "きのう、カレーを3ばいおかわりした", "lie")
    assert result["ok"] and result["player_wins"]
    assert state == {"rounds": 1, "player_wins": 1}


def test_play_b_inappropriate_does_not_count(monkeypatch):
    monkeypatch.setattr(
        game_b,
        "judge_story",
        lambda story: {"is_appropriate": False, "guess": "true", "reason": "書き直してね"},
    )
    state, result = game_b.play_b(None, "きのう、カレーを3ばいおかわりした", "lie")
    assert not result["ok"]
    assert state["rounds"] == 0
