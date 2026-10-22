"""ゲームAのテスト（APIは呼ばない。AIの代わりにダミーの問題を使う）。"""

import pytest

from ai_lie_game import config, game_a
from ai_lie_game.llm import LLMError, extract_json


def fake_quiz(avoid=None):
    return {
        "theme": "どうぶつ",
        "difficulty": "ふつう",
        "statements": ["文1", "文2", "文3"],
        "lie_index": 1,
        "explanation": "解説",
    }


def ai_quiz(statements=None, subjects=None, lie_index=1):
    """AIが返す形の問題データ（品質チェックに通る内容）。"""

    return {
        "statements": statements
        or [
            "カバの汗は赤っぽい色に見えます。",
            "ペンギンは空を飛ぶために羽を使います。",
            "ラッコは寝るときに手をつなぐことがあります。",
        ],
        "subjects": subjects or ["カバ", "ペンギン", "ラッコ"],
        "notes": ["カバの解説", "ペンギンの解説", "ラッコの解説"],
        "lie_index": lie_index,
        "explanation": "ペンギンは空を飛べません。",
        "hint": "その生き物のくらしに合っているか考えよう",
    }


@pytest.fixture
def patched_generate(monkeypatch):
    monkeypatch.setattr(game_a, "generate_quiz", lambda theme, difficulty, avoid=None: fake_quiz())


class FakeLLM:
    """call_llm の代わり。指示文の種類ごとに、用意した応答を順番に返す（validator も通す）。"""

    def __init__(self, quizzes, reviews=None):
        self.quizzes = list(quizzes)
        self.reviews = list(reviews or [])
        self.quiz_prompts = []
        self.review_calls = 0

    def __call__(self, system_prompt, user_prompt, validator=None):
        if system_prompt == game_a.REVIEW_SYSTEM_PROMPT:
            self.review_calls += 1
            data = self.reviews.pop(0)
            if isinstance(data, Exception):
                raise data
        else:
            self.quiz_prompts.append(user_prompt)
            data = self.quizzes.pop(0)
        return validator(data) if validator else data


# --- 既存の検査 ----------------------------------------------------------------


def test_extract_json_with_code_block():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_extract_json_without_json_raises():
    with pytest.raises(ValueError):
        extract_json("JSONではありません")


def test_validate_quiz_ok():
    data = {
        "statements": [" a ", "b", "c"],
        "subjects": ["x", "y", "z"],
        "notes": ["n1", "n2", "n3"],
        "lie_index": "2",
        "explanation": "せつめい",
        "hint": " ヒント ",
    }
    assert game_a.validate_quiz(data) == {
        "statements": ["a", "b", "c"],
        "subjects": ["x", "y", "z"],
        "notes": ["n1", "n2", "n3"],
        "lie_index": 2,
        "explanation": "せつめい",
        "hint": "ヒント",
    }


def test_validate_quiz_hint_is_optional():
    data = ai_quiz()
    del data["hint"]
    assert game_a.validate_quiz(data)["hint"] == ""


@pytest.mark.parametrize(
    "data",
    [
        {"statements": ["a", "b"], "lie_index": 0, "explanation": "x"},
        {"statements": ["a", "b", ""], "lie_index": 0, "explanation": "x"},
        {"statements": ["a", "b", "c"], "lie_index": 3, "explanation": "x"},
        {"statements": ["a", "b", "c"], "lie_index": 0, "explanation": " "},
        {"statements": ["a", "b", "c"], "lie_index": "x", "explanation": "x"},
        # 新しく必須にした項目
        {"statements": ["a", "b", "c"], "lie_index": 0, "explanation": "x", "notes": ["1", "2", "3"]},
        {"statements": ["a", "b", "c"], "lie_index": 0, "explanation": "x", "subjects": ["1", "2", "3"]},
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


def test_difficulty_does_not_ask_for_number_only_lies():
    # 「数字だけを変えたウソ」をAIに求める指示が残っていないこと
    for desc in config.DIFFICULTIES.values():
        assert "数字や細かい部分だけを変えた" not in desc


# --- 品質チェック --------------------------------------------------------------


def test_quality_ok_for_varied_statements():
    assert game_a.find_quality_problems(ai_quiz()) == []


def test_quality_detects_same_subject():
    data = ai_quiz(
        statements=["キリンの体重は約800キロもあります。", "キリンの首の骨は7本です。", "月は少しずつ地球から離れています。"],
        subjects=["キリン", "キリンの首", "月"],
    )
    problems = game_a.find_quality_problems(data)
    assert any("同じ対象" in p for p in problems)


def test_quality_detects_number_only_changes():
    data = ai_quiz(
        statements=["ゾウは1日に150キロの草を食べます。", "ゾウは1日に300キロの草を食べます。", "ゾウは1日に50キロの草を食べます。"],
        subjects=["アフリカゾウ", "インドゾウ", "子どものゾウ"],
    )
    problems = game_a.find_quality_problems(data)
    assert any("よく似ています" in p for p in problems)


def test_quality_detects_same_template():
    data = ai_quiz(
        statements=["カバの汗は赤い色をしています。", "ラクダの汗は青い色をしています。", "パンダの汗は黄色い色をしています。"],
        subjects=["カバ", "ラクダ", "パンダ"],
    )
    assert game_a.find_quality_problems(data)


def test_quality_detects_repeat_of_previous_question():
    data = ai_quiz()
    problems = game_a.find_quality_problems(data, avoid=["カバの汗は、赤っぽい色に見えます"])
    assert any("前に出した" in p for p in problems)


# --- 問題づくり（作り直しと見直し） --------------------------------------------


def test_generate_quiz_shuffles_notes_together(monkeypatch):
    fake = FakeLLM([ai_quiz()], reviews=[{"ok": True, "problems": []}])
    monkeypatch.setattr(game_a, "call_llm", fake)

    for _ in range(10):
        fake.quizzes = [ai_quiz()]
        fake.reviews = [{"ok": True, "problems": []}]
        quiz = game_a.generate_quiz("どうぶつ", "ふつう")
        # シャッフル後も、文・対象・解説の組み合わせと正解がずれていない
        assert quiz["statements"][quiz["lie_index"]] == "ペンギンは空を飛ぶために羽を使います。"
        for s, subject, note in zip(quiz["statements"], quiz["subjects"], quiz["notes"]):
            assert subject in s and note == f"{subject}の解説"
        assert quiz["checked"] is True


def test_generate_quiz_regenerates_with_feedback(monkeypatch):
    bad = ai_quiz(subjects=["カバ", "カバ", "ラッコ"])
    fake = FakeLLM([bad, ai_quiz()], reviews=[{"ok": True, "problems": []}])
    monkeypatch.setattr(game_a, "call_llm", fake)

    quiz = game_a.generate_quiz("どうぶつ", "ふつう")

    assert quiz["checked"] is True
    assert len(fake.quiz_prompts) == 2
    assert "作り直し" in fake.quiz_prompts[1]  # 理由をAIに伝えている
    assert fake.review_calls == 1  # プログラムのチェックに落ちた問題は、AIの見直しをしない（料金の節約）


def test_generate_quiz_regenerates_when_review_finds_problem(monkeypatch):
    fake = FakeLLM(
        [ai_quiz(), ai_quiz()],
        reviews=[{"ok": False, "problems": ["ラッコの文は説が分かれます"]}, {"ok": True, "problems": []}],
    )
    monkeypatch.setattr(game_a, "call_llm", fake)

    quiz = game_a.generate_quiz("どうぶつ", "ふつう")

    assert quiz["checked"] is True
    assert "ラッコの文は説が分かれます" in fake.quiz_prompts[1]


def test_generate_quiz_gives_up_after_max_attempts(monkeypatch):
    bad = ai_quiz(subjects=["カバ", "カバ", "ラッコ"])
    fake = FakeLLM([bad] * config.QUIZ_MAX_ATTEMPTS)
    monkeypatch.setattr(game_a, "call_llm", fake)

    quiz = game_a.generate_quiz("どうぶつ", "ふつう")

    # ゲームは止めずに出題するが、画面に注意書きを出すための印をつける
    assert quiz["checked"] is False
    assert len(fake.quiz_prompts) == config.QUIZ_MAX_ATTEMPTS


def test_generate_quiz_continues_when_review_fails(monkeypatch):
    fake = FakeLLM([ai_quiz()], reviews=[LLMError("つながらない")])
    monkeypatch.setattr(game_a, "call_llm", fake)

    quiz = game_a.generate_quiz("どうぶつ", "ふつう")
    assert quiz["statements"]


def test_generate_quiz_without_review(monkeypatch):
    monkeypatch.setattr(config, "QUIZ_REVIEW_ENABLED", False)
    fake = FakeLLM([ai_quiz()])
    monkeypatch.setattr(game_a, "call_llm", fake)

    game_a.generate_quiz("どうぶつ", "ふつう")
    assert fake.review_calls == 0


# --- 状態とふりかえり ----------------------------------------------------------


def test_new_state_keeps_previous_statements():
    old = game_a.new_state_a("どうぶつ", "ふつう")
    old["used_statements"] = ["前の文"]
    state = game_a.new_state_a("うちゅう", "かんたん", previous=old)
    assert state["used_statements"] == ["前の文"]
    assert state["score"] == 0 and state["history"] == []


def test_summary_lists_mistakes_and_hints(monkeypatch):
    quiz = {**fake_quiz(), "notes": ["n1", "n2", "n3"], "hint": "ヒント"}
    monkeypatch.setattr(game_a, "generate_quiz", lambda theme, difficulty, avoid=None: dict(quiz))

    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    state, _ = game_a.answer_a(state, 0)  # まちがい（本当の「文1」をえらんだ）
    state = game_a.next_question_a(state)
    state, _ = game_a.answer_a(state, 1)  # せいかい

    summary = game_a.summary_a(state)
    assert summary["record"]["score"] == 1 and summary["record"]["total"] == 2
    assert summary["record"]["accuracy"] == 0.5
    assert summary["mistakes"] == [
        {"question_no": 1, "picked_statement": "文1", "picked_note": "n1", "lie_statement": "文2"}
    ]
    assert summary["hints"] == ["ヒント"]


def test_explanation_falls_back_to_lie_note():
    data = ai_quiz()
    del data["explanation"]  # 出題の指示では、もう explanation を書かせない
    result = game_a.validate_quiz(data)
    assert result["explanation"] == "ペンギンの解説"


def test_prompt_no_longer_asks_for_explanation():
    assert '"explanation"' not in game_a.QUIZ_SYSTEM_PROMPT
    assert "少しでも自信がないときは" not in game_a.REVIEW_SYSTEM_PROMPT
