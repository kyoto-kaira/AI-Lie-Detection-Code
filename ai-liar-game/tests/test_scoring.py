from liar_game.difficulty import DIFFICULTIES
from liar_game.scoring import calc_score


def test_wrong_answer_is_zero():
    r = calc_score(DIFFICULTIES["normal"], False, questions_used=3, hints_used=0)
    assert r["score"] == 0


def test_correct_answer_with_bonus():
    d = DIFFICULTIES["normal"]  # 基本200, 最大12問, ボーナス10
    r = calc_score(d, True, questions_used=2, hints_used=0)
    assert r["score"] == 200 + (12 - 2) * 10
    assert r["remaining_questions"] == 10


def test_hint_penalty():
    d = DIFFICULTIES["normal"]  # ヒント減点30
    no_hint = calc_score(d, True, 5, 0)["score"]
    one_hint = calc_score(d, True, 5, 1)["score"]
    assert no_hint - one_hint == 30


def test_score_never_negative():
    d = DIFFICULTIES["hard"]
    r = calc_score(d, True, d.max_questions, 99)
    assert r["score"] == 0


def test_harder_difficulty_gives_higher_max_score():
    def best(key):
        d = DIFFICULTIES[key]
        return calc_score(d, True, 0, 0)["score"]

    assert best("easy") < best("normal") < best("hard")
