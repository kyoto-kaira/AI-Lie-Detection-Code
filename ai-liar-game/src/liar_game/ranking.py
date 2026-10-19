"""ニックネーム別のスコア記録とランキング。

記録は JSON ファイルに保存されます（既定は <プロジェクト>/data/ranking.json）。
保存先は環境変数 LIAR_RANKING_PATH で変更できます。

※このファイルは「ゲームを起動しているパソコン」に保存されます。
  チーム全員で1つのランキングを共有したい場合は、1台がゲームを起動して、
  他の人がそのURLにアクセスする形にしてください（docs/usage.md を参照）。
"""

import json
import os
import threading
from datetime import datetime
from pathlib import Path

from .difficulty import DIFFICULTY_ORDER

MAX_NICKNAME_LENGTH = 12

_lock = threading.Lock()


def default_path() -> Path:
    env = os.getenv("LIAR_RANKING_PATH")
    if env:
        return Path(env)
    # src/liar_game/ranking.py → プロジェクトのルート/data/ranking.json
    return Path(__file__).resolve().parents[2] / "data" / "ranking.json"


def normalize_nickname(nickname: str) -> str:
    """前後の空白を取り除き、長さをチェックする。問題があれば ValueError。"""
    name = (nickname or "").strip()
    if not name:
        raise ValueError("ニックネームを入力してください。")
    if len(name) > MAX_NICKNAME_LENGTH:
        raise ValueError(f"ニックネームは{MAX_NICKNAME_LENGTH}文字以内にしてください。")
    return name


class Ranking:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else default_path()

    # ---- 読み書き ----
    def load(self) -> list[dict]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self, records: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)  # 書き込み途中で壊れないよう、置き換えで保存

    # ---- 追加 ----
    def add(
        self,
        nickname: str,
        difficulty: str,
        score: int,
        is_correct: bool,
        questions_used: int,
        hints_used: int,
    ) -> dict:
        record = {
            "nickname": normalize_nickname(nickname),
            "difficulty": difficulty,
            "score": int(score),
            "is_correct": bool(is_correct),
            "questions_used": int(questions_used),
            "hints_used": int(hints_used),
            "played_at": datetime.now().isoformat(timespec="seconds"),
        }
        with _lock:
            records = self.load()
            records.append(record)
            self._save(records)
        return record

    # ---- 集計 ----
    def best_by_nickname(self, difficulty: str) -> dict[str, int]:
        """指定した難易度での、ニックネームごとのベストスコア。"""
        best: dict[str, int] = {}
        for r in self.load():
            if r.get("difficulty") != difficulty:
                continue
            name = r["nickname"]
            best[name] = max(best.get(name, 0), int(r["score"]))
        return best

    def top(self, difficulty: str | None = None, limit: int = 10) -> list[dict]:
        """ランキング上位を返す。

        difficulty を指定：その難易度でのベストスコア順。
        None（総合）  ：各難易度のベストスコアの合計順。
        """
        if difficulty:
            scores = self.best_by_nickname(difficulty)
        else:
            scores: dict[str, int] = {}
            for key in DIFFICULTY_ORDER:
                for name, s in self.best_by_nickname(key).items():
                    scores[name] = scores.get(name, 0) + s

        ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
        rows = []
        prev_score, prev_rank = None, 0
        for i, (name, s) in enumerate(ordered[:limit], start=1):
            rank = prev_rank if s == prev_score else i  # 同点は同順位
            rows.append({"rank": rank, "nickname": name, "score": s})
            prev_score, prev_rank = s, rank
        return rows

    def rank_of(self, nickname: str, difficulty: str | None = None) -> int | None:
        """ニックネームの現在の順位（記録がなければ None）。"""
        for row in self.top(difficulty, limit=10_000):
            if row["nickname"] == nickname:
                return row["rank"]
        return None
