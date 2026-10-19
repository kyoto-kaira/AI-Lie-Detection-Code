"""取り調べのロジック（質問・証拠の開示・ヒント・推理・スコア）。

画面（Gradio）やAPI通信から切り離してあるので、テストしやすい構造です。
"""

import os

from .cases import get_case, get_liar_id, validate_case
from .difficulty import get_difficulty
from .prompts import create_all_system_prompts
from .scoring import calc_score

DEFAULT_MODEL = "gpt-4o-mini"


def get_model() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def create_client():
    """OpenAIクライアントを作る。APIキーは環境変数 OPENAI_API_KEY から読む。"""
    from openai import OpenAI

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key.startswith("sk-ここに"):
        raise RuntimeError(
            "OPENAI_API_KEY が設定されていません。\n"
            ".env.example を .env にコピーして、APIキーを記入してください。"
        )
    return OpenAI(api_key=api_key)


class GameRuleError(ValueError):
    """質問回数の上限やヒントの上限など、ゲームのルール上できない操作。"""


class InterrogationGame:
    """1プレイ分のゲーム状態を管理する。"""

    def __init__(
        self,
        difficulty: str = "easy",
        nickname: str = "",
        client=None,
        model: str | None = None,
        ranking=None,
    ):
        self.config = get_difficulty(difficulty)
        self.case = get_case(difficulty)
        validate_case(self.case)

        self.nickname = nickname
        self._client = client
        self.model = model or get_model()
        self.ranking = ranking
        self.system_prompts = create_all_system_prompts(self.case, self.config)

        self.histories: dict[str, list[dict]] = {sid: [] for sid in self.case["suspects"]}
        self.questions_used = 0
        self.hints_used = 0
        self.shown_hints: list[str] = []
        self.unlocked_ids: list[str] = []
        self._new_evidence: list[dict] = []
        self.finished = False
        self.result: dict | None = None

        # 最初から見える証拠を開示
        for e in self.case["evidence"]:
            if e["unlock"]["type"] == "start":
                self.unlocked_ids.append(e["id"])

    # ---- クライアント ----
    @property
    def client(self):
        # 初めて質問するときに作る（起動時にAPIキーが無くても画面は開ける）
        if self._client is None:
            self._client = create_client()
        return self._client

    # ---- 状態 ----
    @property
    def remaining_questions(self) -> int:
        return max(self.config.max_questions - self.questions_used, 0)

    @property
    def remaining_hints(self) -> int:
        return max(self.config.max_hints - self.hints_used, 0)

    def suspect_choices(self) -> list[tuple[str, str]]:
        return [
            (f"{sid}：{s['name']}（{s['role']}）", sid) for sid, s in self.case["suspects"].items()
        ]

    def unlocked_evidence(self) -> list[dict]:
        by_id = {e["id"]: e for e in self.case["evidence"]}
        return [by_id[i] for i in self.unlocked_ids]

    @property
    def locked_count(self) -> int:
        return len(self.case["evidence"]) - len(self.unlocked_ids)

    def pop_new_evidence(self) -> list[dict]:
        """直前の質問で新しく見つかった証拠を返し、リストを空にする。"""
        new, self._new_evidence = self._new_evidence, []
        return new

    # ---- 証拠の開示 ----
    def _update_unlocks(self, question: str) -> None:
        for e in self.case["evidence"]:
            if e["id"] in self.unlocked_ids:
                continue
            unlock = e["unlock"]
            hit = False
            if unlock["type"] == "questions":
                hit = self.questions_used >= unlock["count"]
            elif unlock["type"] == "keywords":
                text = question.lower()
                hit = any(w.lower() in text for w in unlock["words"])
                # キーワードに触れなくても、質問を重ねれば（count回で）見つかる
                if not hit and "count" in unlock:
                    hit = self.questions_used >= unlock["count"]
            if hit:
                self.unlocked_ids.append(e["id"])
                self._new_evidence.append(e)

    # ---- 質問 ----
    def ask(self, suspect_id: str, question: str) -> str:
        if self.finished:
            raise GameRuleError("推理は確定済みです。もう一度遊ぶときは「事件を開始」を押してください。")
        if suspect_id not in self.case["suspects"]:
            raise ValueError("容疑者を選んでください。")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("質問を入力してください。")
        if self.remaining_questions <= 0:
            raise GameRuleError("質問できる回数を使い切りました。証拠と証言から推理しましょう。")

        history = self.histories[suspect_id]
        messages = (
            [{"role": "system", "content": self.system_prompts[suspect_id]}]
            + history
            + [{"role": "user", "content": question}]
        )

        response = self.client.chat.completions.create(model=self.model, messages=messages)
        answer = response.choices[0].message.content

        # APIが成功した後でだけ、履歴と回数を更新する
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})
        self.questions_used += 1
        self._update_unlocks(question)
        return answer

    # ---- ヒント ----
    def use_hint(self) -> str:
        if self.finished:
            raise GameRuleError("推理は確定済みです。")
        if self.remaining_hints <= 0:
            raise GameRuleError("ヒントはもう使えません。")
        hints = self.case["hints"]
        hint = hints[min(self.hints_used, len(hints) - 1)]
        self.hints_used += 1
        self.shown_hints.append(hint)
        return hint

    # ---- 推理 ----
    def judge(self, selected_id: str) -> dict:
        if self.finished and self.result:
            return self.result  # 二重登録を防ぐ
        if selected_id not in self.case["suspects"]:
            raise ValueError("嘘つきだと思う人物を選んでください。")

        correct_id = get_liar_id(self.case)
        is_correct = selected_id == correct_id
        breakdown = calc_score(self.config, is_correct, self.questions_used, self.hints_used)

        result = {
            "selected_suspect_id": selected_id,
            "correct_suspect_id": correct_id,
            "is_correct": is_correct,
            "questions_used": self.questions_used,
            "hints_used": self.hints_used,
            **breakdown,
            "rank": None,
        }

        if self.ranking is not None and self.nickname:
            self.ranking.add(
                self.nickname,
                self.config.key,
                result["score"],
                is_correct,
                self.questions_used,
                self.hints_used,
            )
            result["rank"] = self.ranking.rank_of(self.nickname, self.config.key)

        self.finished = True
        self.result = result
        return result

    # ---- 表示用テキスト ----
    def status_text(self) -> str:
        return (
            f"**{self.nickname or 'ゲスト'}** さん ／ 難易度：{self.config.label} ／ "
            f"残り質問：**{self.remaining_questions}**/{self.config.max_questions} ／ "
            f"ヒント：**{self.remaining_hints}**/{self.config.max_hints}"
        )

    def evidence_markdown(self) -> str:
        lines = [f"- **{e['id']}：{e['name']}**　{e['description']}" for e in self.unlocked_evidence()]
        if self.locked_count > 0 and not self.finished:
            lines.append(
                f"- 🔒 まだ見つかっていない証拠が **{self.locked_count}件** あります。"
                "気になることを具体的に質問すると、新しい証拠が見つかるかもしれません。"
            )
        return "\n".join(lines)

    def feedback_text(self, result: dict) -> str:
        suspects = self.case["suspects"]
        selected = suspects[result["selected_suspect_id"]]["name"]
        liar = suspects[result["correct_suspect_id"]]

        lines = []
        if result["is_correct"]:
            lines.append(f"## 🎉 正解です！\n{selected}が嘘をついていました。")
            lines.append(
                f"\n**スコア：{result['score']}点**　"
                f"（基本 {result['base']} ＋ 質問ボーナス {result['question_bonus']} "
                f"− ヒント減点 {result['hint_penalty']}）"
            )
        else:
            lines.append(
                f"## 残念、不正解です\nあなたが選んだ人物：{selected}\n\n正解：{liar['name']}"
            )
            lines.append("\n**スコア：0点**")
        if result.get("rank"):
            lines.append(f"\n現在の順位（{self.config.label}）：**{result['rank']}位**")

        lines.append("\n### 事件の解説")
        lines.append(self.case["solution"]["summary"])
        for i, step in enumerate(self.case["solution"]["logic"], start=1):
            lines.append(f"{i}. {step}")

        secrets = [
            (s["name"], t) for s in suspects.values() if not s["is_liar"] for t in s.get("secrets", [])
        ]
        if secrets:
            lines.append("\n### 無実の人が隠していたこと")
            for name, text in secrets:
                lines.append(f"- {name}：{text}")

        lines.append("\n### すべての証拠")
        for e in self.case["evidence"]:
            mark = "" if e["id"] in self.unlocked_ids else "（未発見）"
            lines.append(f"- **{e['id']}：{e['name']}**{mark}　{e['description']}")
        return "\n".join(lines)
