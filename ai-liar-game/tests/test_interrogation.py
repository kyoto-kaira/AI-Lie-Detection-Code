from types import SimpleNamespace

import pytest

from liar_game.interrogation import GameRuleError, InterrogationGame
from liar_game.ranking import Ranking


class FakeClient:
    """OpenAI APIの代わりに固定の返答をするダミー（APIキー・課金不要でテストできる）。"""

    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model, messages):
        if self.fail:
            raise RuntimeError("API error")
        self.calls.append(messages)
        msg = SimpleNamespace(content="テスト回答")
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def make(difficulty="easy", **kw):
    return InterrogationGame(difficulty, client=FakeClient(), **kw)


# ---- 質問 ----
def test_ask_updates_history_and_count():
    game = make()
    assert game.ask("B", "どこにいましたか？") == "テスト回答"
    assert len(game.histories["B"]) == 2
    assert game.histories["A"] == []
    assert game.questions_used == 1
    assert game.remaining_questions == game.config.max_questions - 1


def test_history_is_sent_on_second_question():
    client = FakeClient()
    game = InterrogationGame("easy", client=client)
    game.ask("B", "1つ目")
    game.ask("B", "2つ目")
    assert len(client.calls[1]) == 4  # system + (user, assistant) + user
    assert client.calls[1][0]["role"] == "system"


def test_failed_api_call_is_not_counted():
    game = InterrogationGame("easy", client=FakeClient(fail=True))
    with pytest.raises(RuntimeError):
        game.ask("A", "質問")
    assert game.histories["A"] == []
    assert game.questions_used == 0


def test_invalid_input():
    game = make()
    with pytest.raises(ValueError):
        game.ask("Z", "質問")
    with pytest.raises(ValueError):
        game.ask("A", "   ")
    assert game.questions_used == 0


def test_question_limit():
    game = make("easy")
    for _ in range(game.config.max_questions):
        game.ask("A", "質問")
    assert game.remaining_questions == 0
    with pytest.raises(GameRuleError):
        game.ask("A", "もう1問")


def test_each_difficulty_uses_its_own_case():
    assert len(make("hard").case["suspects"]) == 4
    assert make("easy").case["case_id"] == "museum_001"


# ---- 証拠の開示 ----
def test_easy_has_all_evidence_at_start():
    game = make("easy")
    assert len(game.unlocked_evidence()) == 3
    assert game.locked_count == 0


def test_normal_starts_with_one_evidence():
    game = make("normal")
    assert [e["id"] for e in game.unlocked_evidence()] == ["E1"]
    assert game.locked_count == 3


def test_keyword_unlocks_evidence():
    game = make("normal")
    game.ask("B", "あなたのパソコンの作業ログを教えてください")
    new = game.pop_new_evidence()
    assert [e["id"] for e in new] == ["E2"]
    assert game.pop_new_evidence() == []  # 一度取り出したら空になる
    assert game.locked_count == 2


def test_unrelated_question_does_not_unlock_early():
    game = make("normal")
    game.ask("A", "こんばんは")
    assert game.pop_new_evidence() == []
    assert [e["id"] for e in game.unlocked_evidence()] == ["E1"]


def test_evidence_unlocks_by_question_count():
    game = make("normal")
    for _ in range(4):  # E2 は count=4
        game.ask("A", "こんばんは")
    assert "E2" in game.unlocked_ids


def test_all_evidence_eventually_found_within_budget():
    for key in ("easy", "normal", "hard"):
        game = make(key)
        for _ in range(game.config.max_questions):
            game.ask("A", "こんばんは")
        assert game.locked_count == 0, key


# ---- ヒント ----
def test_hints_are_progressive_and_limited():
    game = make("normal")  # ヒント2回
    h1 = game.use_hint()
    h2 = game.use_hint()
    assert h1 != h2
    assert game.remaining_hints == 0
    with pytest.raises(GameRuleError):
        game.use_hint()


# ---- 推理・スコア・ランキング ----
def test_judge_correct_scores_and_blocks_further_play():
    game = make("normal")
    game.ask("B", "こんばんは")
    result = game.judge("B")
    assert result["is_correct"] and result["score"] == 200 + 11 * 10
    assert game.finished
    with pytest.raises(GameRuleError):
        game.ask("A", "もう質問")


def test_judge_wrong_is_zero():
    game = make("easy")
    result = game.judge("A")
    assert not result["is_correct"] and result["score"] == 0


def test_judge_unknown_suspect():
    with pytest.raises(ValueError):
        make().judge("Z")


def test_judge_is_idempotent(tmp_path):
    ranking = Ranking(tmp_path / "r.json")
    game = make("easy", nickname="たろう", ranking=ranking)
    first = game.judge("B")
    second = game.judge("A")  # 確定後に別の人を選んでも結果は変わらない
    assert first == second
    assert len(ranking.load()) == 1  # 二重登録されない


def test_judge_registers_in_ranking(tmp_path):
    ranking = Ranking(tmp_path / "r.json")
    game = make("easy", nickname="たろう", ranking=ranking)
    result = game.judge("B")
    assert result["rank"] == 1
    assert ranking.top("easy")[0]["nickname"] == "たろう"


def test_no_ranking_without_nickname(tmp_path):
    ranking = Ranking(tmp_path / "r.json")
    game = make("easy", nickname="", ranking=ranking)
    game.judge("B")
    assert ranking.load() == []


# ---- 表示 ----
def test_texts():
    game = make("normal", nickname="たろう")
    assert "たろう" in game.status_text()
    assert "E1" in game.evidence_markdown() and "3件" in game.evidence_markdown()
    text = game.feedback_text(game.judge("A"))
    assert "不正解" in text and "中村" in text
    assert "（未発見）" in text  # 見つけていない証拠も解説で全公開


def test_feedback_reveals_innocent_secrets_in_hard():
    game = make("hard")
    text = game.feedback_text(game.judge("D"))
    assert "正解です" in text
    assert "保険" in text and "ワイン" in text
