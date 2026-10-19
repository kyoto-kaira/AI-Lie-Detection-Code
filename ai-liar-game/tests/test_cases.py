import copy

import pytest

from liar_game.cases import CASES, get_case, get_liar_id, validate_case
from liar_game.difficulty import DIFFICULTIES, DIFFICULTY_ORDER
from liar_game.prompts import create_system_prompt

EXPECTED_LIAR = {"easy": "B", "normal": "B", "hard": "D"}


@pytest.mark.parametrize("key", DIFFICULTY_ORDER)
def test_every_case_is_valid(key):
    validate_case(get_case(key))


@pytest.mark.parametrize("key", DIFFICULTY_ORDER)
def test_liar_id(key):
    assert get_liar_id(get_case(key)) == EXPECTED_LIAR[key]


def test_suspect_counts():
    assert len(get_case("easy")["suspects"]) == 3
    assert len(get_case("normal")["suspects"]) == 3
    assert len(get_case("hard")["suspects"]) == 4


def test_get_case_returns_a_copy():
    case = get_case("easy")
    case["suspects"]["B"]["is_liar"] = False
    case["evidence"].clear()
    # 元データは変わらない（事件は不変）
    assert get_liar_id(get_case("easy")) == "B"
    assert len(get_case("easy")["evidence"]) == 3


def test_unknown_case():
    with pytest.raises(ValueError):
        get_case("impossible")


def test_two_liars_is_rejected():
    broken = get_case("normal")
    broken["suspects"]["A"]["is_liar"] = True
    with pytest.raises(AssertionError):
        validate_case(broken)


def test_unknown_evidence_reference_is_rejected():
    broken = copy.deepcopy(get_case("hard"))
    broken["suspects"]["D"]["contradicted_by"] = ["E99"]
    with pytest.raises(AssertionError):
        validate_case(broken)


def test_easy_shows_all_evidence_from_start():
    assert all(e["unlock"]["type"] == "start" for e in CASES["easy"]["evidence"])


@pytest.mark.parametrize("key", ["normal", "hard"])
def test_harder_cases_hide_some_evidence(key):
    types = [e["unlock"]["type"] for e in CASES[key]["evidence"]]
    assert "start" in types and "keywords" in types


@pytest.mark.parametrize("key", DIFFICULTY_ORDER)
def test_evidence_unlocks_within_question_budget(key):
    """質問回数の上限内で、すべての証拠が見つけられること（詰みの防止）。"""
    limit = DIFFICULTIES[key].max_questions
    for e in CASES[key]["evidence"]:
        unlock = e["unlock"]
        if unlock["type"] != "start":
            assert unlock["count"] <= limit


def test_difficulty_scales():
    easy, normal, hard = (DIFFICULTIES[k] for k in DIFFICULTY_ORDER)
    assert easy.max_hints > normal.max_hints > hard.max_hints
    assert easy.base_score < normal.base_score < hard.base_score


# ---- プロンプト ----
def test_easy_liar_prompt_confesses_under_pressure():
    case = get_case("easy")
    prompt = create_system_prompt(case, "B", DIFFICULTIES["easy"])
    assert "あなたは嘘つきです" in prompt
    assert "ずっとカフェにいた" in prompt
    assert "素直に認めて" in prompt
    assert "うっかり口にしてしまうこと" not in prompt


def test_normal_liar_prompt_has_cover_lie_and_slip():
    case = get_case("normal")
    prompt = create_system_prompt(case, "B", DIFFICULTIES["normal"])
    assert "嘘を補強するための嘘" in prompt
    assert "マスターカードは昼のうちに" in prompt
    assert "青いケース" in prompt
    assert "言い訳やごまかし" in prompt


def test_hard_liar_prompt_resists():
    case = get_case("hard")
    prompt = create_system_prompt(case, "D", DIFFICULTIES["hard"])
    assert "簡単には認めないで" in prompt
    assert "薪を1本くべた" in prompt
    assert "赤いルビー" in prompt


def test_innocent_with_secret_dodges_but_does_not_lie():
    case = get_case("hard")
    prompt = create_system_prompt(case, "B", DIFFICULTIES["hard"])
    assert "隠していること" in prompt
    assert "はぐらかして" in prompt
    assert "嘘はつかないでください" in prompt
    assert "あなたは嘘つきです" not in prompt


def test_honest_prompt_without_secret():
    case = get_case("easy")
    prompt = create_system_prompt(case, "A", DIFFICULTIES["easy"])
    assert "あなたは嘘をついていない人物です" in prompt
    assert "隠していること" not in prompt
