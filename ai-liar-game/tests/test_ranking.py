import json

import pytest

from liar_game.ranking import MAX_NICKNAME_LENGTH, Ranking, normalize_nickname


@pytest.fixture
def ranking(tmp_path):
    return Ranking(tmp_path / "data" / "ranking.json")


def add(r, name, diff, score):
    return r.add(name, diff, score, is_correct=score > 0, questions_used=3, hints_used=0)


def test_empty_ranking(ranking):
    assert ranking.load() == []
    assert ranking.top("easy") == []
    assert ranking.rank_of("ゆうこ", "easy") is None


def test_add_creates_file_and_persists(ranking):
    add(ranking, "ゆうこ", "easy", 150)
    assert ranking.path.exists()
    data = json.loads(ranking.path.read_text(encoding="utf-8"))
    assert data[0]["nickname"] == "ゆうこ" and data[0]["score"] == 150
    # 別インスタンスでも読める
    assert Ranking(ranking.path).top("easy")[0]["nickname"] == "ゆうこ"


def test_top_orders_by_best_score_per_nickname(ranking):
    add(ranking, "A", "easy", 100)
    add(ranking, "A", "easy", 170)  # 同じ人はベストのみ
    add(ranking, "B", "easy", 150)
    top = ranking.top("easy")
    assert [(r["nickname"], r["score"]) for r in top] == [("A", 170), ("B", 150)]
    assert [r["rank"] for r in top] == [1, 2]


def test_ties_share_rank(ranking):
    add(ranking, "A", "easy", 100)
    add(ranking, "B", "easy", 100)
    add(ranking, "C", "easy", 50)
    assert [r["rank"] for r in ranking.top("easy")] == [1, 1, 3]


def test_difficulty_filter(ranking):
    add(ranking, "A", "easy", 100)
    add(ranking, "A", "hard", 400)
    assert [r["score"] for r in ranking.top("easy")] == [100]
    assert [r["score"] for r in ranking.top("hard")] == [400]


def test_overall_is_sum_of_bests(ranking):
    add(ranking, "A", "easy", 100)
    add(ranking, "A", "easy", 120)
    add(ranking, "A", "hard", 300)
    add(ranking, "B", "normal", 500)
    top = ranking.top(None)
    assert [(r["nickname"], r["score"]) for r in top] == [("B", 500), ("A", 420)]


def test_limit(ranking):
    for i in range(15):
        add(ranking, f"p{i:02d}", "easy", i)
    assert len(ranking.top("easy", limit=10)) == 10


def test_corrupted_file_is_treated_as_empty(ranking):
    ranking.path.parent.mkdir(parents=True)
    ranking.path.write_text("{broken", encoding="utf-8")
    assert ranking.load() == []
    add(ranking, "A", "easy", 10)  # 壊れていても追記できる
    assert len(ranking.load()) == 1


def test_nickname_validation():
    assert normalize_nickname("  たろう ") == "たろう"
    with pytest.raises(ValueError):
        normalize_nickname("   ")
    with pytest.raises(ValueError):
        normalize_nickname("あ" * (MAX_NICKNAME_LENGTH + 1))
