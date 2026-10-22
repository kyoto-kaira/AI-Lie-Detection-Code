"""ゲームAの先読み（次の問題を裏で作っておく）のテスト（APIは呼ばない）。"""

import threading
import time

import pytest

from ai_lie_game import config, game_a, ui


class FakeGenerator:
    """generate_quiz の代わり。呼ばれた回数と、受け取った avoid を記録する。delay 秒かけて問題を作る。"""

    def __init__(self, delay=0.0, fail_first=False):
        self.delay = delay
        self.fail_first = fail_first
        self.calls = []
        self.lock = threading.Lock()

    def __call__(self, theme, difficulty, avoid=None):
        with self.lock:
            n = len(self.calls) + 1
            self.calls.append(list(avoid or []))
        time.sleep(self.delay)
        if self.fail_first and n == 1:
            raise game_a.LLMError("つながらない")
        return {
            "theme": theme,
            "difficulty": difficulty,
            "statements": [f"q{n}-文1", f"q{n}-文2", f"q{n}-文3"],
            "subjects": ["a", "b", "c"],
            "notes": ["n1", "n2", "n3"],
            "lie_index": 1,
            "explanation": "解説",
            "hint": "ヒント",
            "checked": True,
        }


@pytest.fixture
def gen(monkeypatch):
    def install(**kwargs):
        fake = FakeGenerator(**kwargs)
        monkeypatch.setattr(game_a, "generate_quiz", fake)
        return fake

    return install


def wait_prefetch(state):
    job = game_a._prefetch_jobs.get(state["game_id"])
    if job:
        job[1].result(timeout=5)


def wait_prefetch_safe(state):
    job = game_a._prefetch_jobs.get(state["game_id"])
    if job:
        try:
            job[1].result(timeout=5)
        except Exception:
            pass


def test_prefetched_question_is_used(gen):
    fake = gen()
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    assert game_a.start_prefetch_a(state) is True
    assert game_a.start_prefetch_a(state) is False  # 2回目は何もしない
    wait_prefetch(state)

    state = game_a.next_question_a(state)

    assert state["prefetch_status"] == "間に合った"
    assert state["current_quiz"]["statements"][0] == "q2-文1"
    assert len(fake.calls) == 2  # 1問目と、先読みした2問目だけ（むだな呼び出しなし）
    assert "q1-文1" in fake.calls[1]  # 先読みでも、1問目の文を避けるよう伝えている


def test_prefetch_disabled_keeps_old_behavior(gen, monkeypatch):
    monkeypatch.setattr(config, "PREFETCH_ENABLED", False)
    fake = gen()
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    assert game_a.start_prefetch_a(state) is False

    state = game_a.next_question_a(state)
    assert state["prefetch_status"] == "なし"
    assert len(fake.calls) == 2


def test_prefetch_failure_falls_back_to_normal_generation(gen):
    fake = gen(fail_first=False)
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    fake.fail_first = True
    fake.calls.clear()  # 次の呼び出し（先読み）を1回目として失敗させる
    game_a.start_prefetch_a(state)
    wait_prefetch_safe(state)

    state = game_a.next_question_a(state)
    assert state["prefetch_status"] == "失敗"
    assert state["question_no"] == 2  # その場で作り直して、ゲームは続く
    assert len(fake.calls) == 2


def test_no_prefetch_after_last_question(gen, monkeypatch):
    monkeypatch.setattr(config, "NUM_QUESTIONS", 1)
    gen()
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    assert game_a.start_prefetch_a(state) is False


def test_new_game_cancels_old_prefetch(gen):
    gen()
    old = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    game_a.start_prefetch_a(old)
    assert old["game_id"] in game_a._prefetch_jobs

    new = game_a.new_state_a("うちゅう", "かんたん", previous=old)
    assert old["game_id"] not in game_a._prefetch_jobs
    assert new["game_id"] != old["game_id"]


def test_prefetch_for_wrong_question_is_ignored(gen):
    fake = gen()
    state = game_a.next_question_a(game_a.new_state_a("どうぶつ", "ふつう"))
    game_a.start_prefetch_a(state)
    wait_prefetch(state)
    state["question_no"] += 1  # 予定とちがう問題番号になった（ふつうは起きない）

    state = game_a.next_question_a(state)
    assert state["prefetch_status"] == "なし"
    assert len(fake.calls) == 3


def test_full_game_through_ui_uses_every_prefetch(gen):
    fake = gen()
    state = ui.ui_start_a("どうぶつ", "ふつう", None)[0]
    for _ in range(config.NUM_QUESTIONS - 1):
        wait_prefetch(state)
        state = ui.ui_answer_a(1, state)[0]
        state = ui.ui_next_a(state)[0]
        assert state["prefetch_status"] == "間に合った"
    state = ui.ui_answer_a(1, state)[0]
    out = ui.ui_next_a(state)

    assert "おしまい" in out[1]
    assert out[0]["score"] == config.NUM_QUESTIONS  # スコア集計は変わらない
    assert len(fake.calls) == config.NUM_QUESTIONS  # 問題づくりの回数は先読みなしと同じ


def test_wait_is_shorter_with_prefetch(gen, monkeypatch, capsys):
    """問題づくりに 0.6秒かかる偽のAIで、参加者が 0.4秒考えたときの待ち時間を比べる。"""

    def play(prefetch):
        monkeypatch.setattr(config, "PREFETCH_ENABLED", prefetch)
        gen(delay=0.6)
        state = ui.ui_start_a("どうぶつ", "ふつう", None)[0]
        time.sleep(0.4)  # 参加者が考えている時間
        state = ui.ui_answer_a(0, state)[0]
        t = time.perf_counter()
        ui.ui_next_a(state)
        return time.perf_counter() - t

    without = play(False)
    with_prefetch = play(True)

    assert without >= 0.55  # 押してから作るので、ほぼまるごと待つ
    assert with_prefetch <= 0.4  # 考えている間に作り進めた分だけ短くなる
    assert "[timing]" in capsys.readouterr().out
