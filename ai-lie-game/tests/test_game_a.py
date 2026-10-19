"""ゲームAのテスト（APIは呼ばない。AIの代わりにダミーの問題を使う）。"""

import pytest

from ai_lie_game import config, game_a
from ai_lie_game.llm import extract_json


def fake_quiz(avoid=None):
    return {
        "theme": "どうぶつ",
        "difficulty": "ふつう",
        "statements": ["文1", "文2", "文3"],
        "lie_index": 1,
        "explanation": "解説",
    }


@pytest.fixture
def patched_generate(monkeypatch):
    monkeypatch.setattr(game_a, "generate_quiz", lambda theme, difficulty, avoid=None: fake_quiz())


def test_extract_json_with_code_block():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_without_json_raises():
    with pytest.raises(ValueError):
        extract_json("JSONではありません")


def test_validate_quiz_ok():
    data = {"statements": [" a ", "b", "c"], "lie_index": "2", "explanation": "せつめい"}
    assert game_a.validate_quiz(data) == {
        "statements": ["a", "b", "c"],
        "lie_index": 2,
        "explanation": "せつめい",
    }


@pytest.mark.parametrize(
    "data",
    [
        {"statements": ["a", "b"], "lie_index": 0, "explanation": "x"},
        {"statements": ["a", "b", ""], "lie_index": 0, "explanation": "x"},
        {"statements": ["a", "b", "c"], "lie_index": 3, "explanation": "x"},
        {"statements": ["a", "b", "c"], "lie_index": 0, "explanation": " "},
    ],
)
def test_validate_quiz_invalid(data):
    with pytest.raises(ValueError):
        game_a.validate_quiz(data)


def test_check_answer():
    quiz = fake_quiz()
    assert game_a.check_answer(quiz, 1)["is_correct"] is True
    assert game_a.check_answer(quiz, 0)["is_correct"] is False


def test_full_game_flow(patched_generate):
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    assert state["question_no"] == 1

    for _ in range(config.NUM_QUESTIONS):
        state, result = game_a.answer_a(state, 1)  # 正解を選び続ける
        assert result is not None
        # 同じ問題への2回目の回答は無視される
        assert game_a.answer_a(state, 1)[1] is None
        if state["finished"]:
            break
        state = game_a.next_question_a(state)

    assert state["finished"] is True
    assert state["score"] == config.NUM_QUESTIONS


def test_final_message_levels():
    assert "パーフェクト" in game_a.final_message_a(config.NUM_QUESTIONS)
    assert "ざんねん" not in game_a.final_message_a(0)
