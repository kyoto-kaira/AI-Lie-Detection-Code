"""Gradio の画面定義。"""

import gradio as gr

from .difficulty import DIFFICULTIES, DIFFICULTY_ORDER, difficulty_choices
from .interrogation import GameRuleError, InterrogationGame
from .ranking import MAX_NICKNAME_LENGTH, Ranking, normalize_nickname

HOW_TO = """
**遊び方**
1. ニックネームと難易度を選んで「事件を開始」を押します。
2. 容疑者に質問して、証言を集めます。**質問できる回数には上限**があります。
3. 気になることを具体的に聞くと、**新しい証拠が見つかる**ことがあります。
4. 嘘をついている人物（＝犯人）が分かったら「推理を確定する」を押します。

**推理のコツ（ミステリーのお約束）**
- **アリバイ**：「いつ・どこで・誰と」を整理し、証言と証拠の時刻を照らし合わせる。
- **証言 vs 記録**：「ずっと〜していた」は、1か所でも崩れれば全体が怪しくなる。
- **補強の嘘**：嘘を支えるための細かい話は、第三者の証言や記録で確かめられることが多い。
- **秘密の暴露**：犯人しか知り得ない情報を、うっかり口にしていないか。
- **隠し事 ≠ 嘘**：無実の人にも、人に言いたくない事情はある。惑わされないこと。

**スコア**：正解すると「基本点 ＋ 残り質問ボーナス − ヒント減点」。不正解は0点。
ランキングには、ニックネームごとの**ベストスコア**が載ります。
助手の**ミナト**は、答えは言いませんが、ヒントをくれます（回数制限・減点あり）。
"""


def _paragraphs(text: str) -> str:
    """インデント付きの複数行テキストを、Markdownで崩れない形に整える。"""
    return "  \n".join(line.strip() for line in text.strip().splitlines() if line.strip())


def _chat_view(game: InterrogationGame, suspect_id: str) -> list[dict]:
    return list(game.histories[suspect_id])


def _hint_markdown(game: InterrogationGame) -> str:
    if not game.shown_hints:
        return ""
    lines = ["**🧑‍💼 助手ミナトのヒント**"]
    lines += [f"{i}. {h}" for i, h in enumerate(game.shown_hints, start=1)]
    return "\n".join(lines)


def build_app(client=None, ranking: Ranking | None = None) -> gr.Blocks:
    ranking = ranking or Ranking()

    def rank_rows(kind: str) -> list[list]:
        difficulty = None if kind == "all" else kind
        return [[r["rank"], r["nickname"], r["score"]] for r in ranking.top(difficulty, limit=20)]

    with gr.Blocks(title="AI嘘発見ゲーム") as demo:
        # ブラウザのタブ(セッション)ごとに別のゲーム状態を持つ
        state = gr.State(None)

        gr.Markdown("# 🔍 AI嘘発見ゲーム")
        gr.Markdown("容疑者役のAIに質問して証言の矛盾を見つけ、嘘をついている人物を当てよう。")

        with gr.Tabs():
            # ======================= 事件を解くタブ =======================
            with gr.Tab("🕵️ 事件を解く"):
                with gr.Accordion("遊び方・推理のコツ", open=False):
                    gr.Markdown(HOW_TO)

                with gr.Row():
                    nickname = gr.Textbox(
                        label=f"ニックネーム（{MAX_NICKNAME_LENGTH}文字まで）",
                        placeholder="例：ホームズ",
                        max_lines=1,
                        scale=2,
                    )
                    difficulty = gr.Radio(
                        difficulty_choices(), value="easy", label="難易度", scale=3
                    )
                diff_desc = gr.Markdown(DIFFICULTIES["easy"].description)
                start = gr.Button("事件を開始 / やり直す", variant="primary")

                with gr.Column(visible=False) as play_area:
                    case_md = gr.Markdown()
                    status_md = gr.Markdown()
                    with gr.Row():
                        with gr.Column(scale=2):
                            suspect = gr.Dropdown(label="質問する容疑者", interactive=True)
                            chatbot = gr.Chatbot(type="messages", label="取り調べ", height=360)
                            question = gr.Textbox(
                                label="質問",
                                placeholder="例：19時15分にはどこにいましたか？",
                                max_lines=1,
                            )
                            send = gr.Button("質問する", variant="primary")
                        with gr.Column(scale=1):
                            gr.Markdown("### 🗂 証拠")
                            evidence_md = gr.Markdown()
                            hint_btn = gr.Button("🧑‍💼 助手ミナトにヒントを聞く")
                            hint_md = gr.Markdown()
                            gr.Markdown("### 最終推理")
                            guess = gr.Radio(label="嘘をついていると思う人物")
                            judge = gr.Button("推理を確定する")
                    result_md = gr.Markdown()

            # ======================= ランキングタブ =======================
            with gr.Tab("🏆 ランキング") as rank_tab:
                rank_kind = gr.Radio(
                    [("総合（各難易度のベスト合計）", "all")] + difficulty_choices(),
                    value="all",
                    label="表示する種類",
                )
                rank_table = gr.Dataframe(
                    headers=["順位", "ニックネーム", "スコア"],
                    datatype=["number", "str", "number"],
                    value=rank_rows("all"),
                    interactive=False,
                )
                refresh = gr.Button("更新")

        # ------------------------- イベント処理 -------------------------
        def on_difficulty_change(key):
            return DIFFICULTIES[key].description

        def on_start(nick, diff):
            try:
                name = normalize_nickname(nick)
            except ValueError as e:
                raise gr.Error(str(e))

            game = InterrogationGame(diff, nickname=name, client=client, ranking=ranking)
            first = next(iter(game.case["suspects"]))
            return (
                game,
                gr.update(visible=True),
                f"## {game.case['case_title']}\n{_paragraphs(game.case['case_description'])}",
                game.status_text(),
                gr.update(choices=game.suspect_choices(), value=first),
                [],
                "",
                game.evidence_markdown(),
                "",
                gr.update(choices=game.suspect_choices(), value=None),
                "",
            )

        def on_send(game, suspect_id, q):
            if game is None:
                raise gr.Error("先に「事件を開始」を押してください。")
            ok = False
            try:
                game.ask(suspect_id, q)
                ok = True
            except (GameRuleError, ValueError) as e:
                gr.Warning(str(e))
            except Exception as e:  # APIキー未設定・通信エラーなど
                gr.Warning(f"回答の取得中にエラーが発生しました：{e}")

            for ev in game.pop_new_evidence():
                gr.Info(f"🔎 新しい証拠が見つかりました：{ev['id']} {ev['name']}")
            return (
                _chat_view(game, suspect_id),
                "" if ok else q,  # 失敗したときは入力した質問を残す
                game.status_text(),
                game.evidence_markdown(),
            )

        def on_switch(game, suspect_id):
            if game is None or not suspect_id:
                return []
            return _chat_view(game, suspect_id)

        def on_hint(game):
            if game is None:
                raise gr.Error("先に「事件を開始」を押してください。")
            try:
                game.use_hint()
            except GameRuleError as e:
                gr.Warning(str(e))
            return _hint_markdown(game), game.status_text()

        def on_judge(game, selected):
            if game is None:
                raise gr.Error("先に「事件を開始」を押してください。")
            if not selected:
                gr.Warning("嘘をついていると思う人物を選んでください。")
                return gr.skip(), gr.skip(), gr.skip()
            result = game.judge(selected)
            return game.feedback_text(result), game.status_text(), game.evidence_markdown()

        def on_rank(kind):
            return rank_rows(kind)

        difficulty.change(on_difficulty_change, difficulty, diff_desc)
        start.click(
            on_start,
            [nickname, difficulty],
            [
                state, play_area, case_md, status_md, suspect, chatbot,
                question, evidence_md, hint_md, guess, result_md,
            ],
        )
        ask_outputs = [chatbot, question, status_md, evidence_md]
        send.click(on_send, [state, suspect, question], ask_outputs)
        question.submit(on_send, [state, suspect, question], ask_outputs)
        suspect.change(on_switch, [state, suspect], chatbot)
        hint_btn.click(on_hint, state, [hint_md, status_md])
        judge.click(on_judge, [state, guess], [result_md, status_md, evidence_md])

        rank_kind.change(on_rank, rank_kind, rank_table)
        refresh.click(on_rank, rank_kind, rank_table)
        rank_tab.select(on_rank, rank_kind, rank_table)

    return demo
