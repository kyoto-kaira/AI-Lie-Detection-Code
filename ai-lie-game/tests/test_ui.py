"""画面処理のテスト（APIは呼ばない）。各処理が、画面の部品の数と同じ数の値を返すかを確かめる。"""

from ai_lie_game import config, game_a, game_b, ui
from tests.test_game_b import FakeDetective, ask, judge

OUTPUTS_A = 7
OUTPUTS_B = 11


def fake_quiz(theme, difficulty, avoid=None):
    return {
        "theme": theme,
        "difficulty": difficulty,
        "statements": ["文1", "文2", "文3"],
        "subjects": ["a", "b", "c"],
        "notes": ["n1", "n2", "n3"],
        "lie_index": 1,
        "explanation": "解説",
        "hint": "ヒント",
        "checked": False,
    }


def test_md_escape():
    assert ui.md_escape("**太字**[link](x)") == r"\*\*太字\*\*\[link\]\(x\)"


def test_game_a_screens(monkeypatch):
    monkeypatch.setattr(game_a, "generate_quiz", fake_quiz)

    out = ui.ui_start_a("どうぶつ", "ふつう", None)
    assert len(out) == OUTPUTS_A
    state = out[0]

    out = ui.ui_answer_a(0, state)
    assert len(out) == OUTPUTS_A
    text = out[3]
    assert "ざんねん" in text and "n2" in text and "ヒント" in text
    assert "あなたがえらんだもの" in text
    assert "気になるところが残った" in text  # checked=False の注意書き

    for _ in range(config.NUM_QUESTIONS - 1):
        state = ui.ui_next_a(state)[0]
        state = ui.ui_answer_a(1, state)[0]

    out = ui.ui_next_a(state)
    assert len(out) == OUTPUTS_A
    summary = out[1]
    assert "おしまい" in summary and "ふりかえり" in summary and "AIについて" in summary


def test_game_a_next_game_keeps_history(monkeypatch):
    monkeypatch.setattr(game_a, "generate_quiz", fake_quiz)
    state = ui.ui_start_a("どうぶつ", "ふつう", None)[0]
    state = ui.ui_start_a("どうぶつ", "ふつう", state)[0]
    assert state["used_statements"].count("文1") == 2


def test_game_b_screens(monkeypatch):
    monkeypatch.setattr(game_b, "call_llm", FakeDetective(ask("何味？"), judge("true")))

    out = ui.ui_start_b("lie", "きのう、カレーを3ばいおかわりした", None)
    assert len(out) == OUTPUTS_B
    state = out[0]
    assert "何味？" in out[4]

    out = ui.ui_skip_b(state)
    assert len(out) == OUTPUTS_B
    state = out[0]
    assert "もういちど聞くね" in out[4]

    out = ui.ui_answer_b("あまくち", state)
    assert len(out) == OUTPUTS_B
    assert "あなたの勝ち" in out[9] and "推測" in out[9]
    assert "かいすうには数えない" in out[4] and "あまくち" in out[4]
    assert "あなた 1 かち" in out[10]


def test_game_b_messages_and_reset(monkeypatch):
    out = ui.ui_start_b(None, "きのう、カレーを3ばいおかわりした", None)
    assert len(out) == OUTPUTS_B and "こっそり" in out[9]

    monkeypatch.setattr(game_b, "call_llm", FakeDetective(ask("何味？")))
    state = ui.ui_start_b("lie", "きのう、カレーを3ばいおかわりした", None)[0]
    out = ui.ui_reset_b(state)
    assert len(out) == OUTPUTS_B
    assert out[0]["phase"] == "idle" and out[0]["rounds"] == 0
