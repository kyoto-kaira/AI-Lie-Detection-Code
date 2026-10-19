"""画面（Gradio）（Colabのセル7に相当）。画面の組み立ては build_demo() にまとめている。"""

import gradio as gr

from ai_lie_game import config
from ai_lie_game.game_a import (
    answer_a,
    final_message_a,
    new_state_a,
    next_question_a,
)
from ai_lie_game.game_b import TRUTH_LABELS, new_state_b, play_b
from ai_lie_game.llm import LLMError

NUM_QUESTIONS = config.NUM_QUESTIONS

RULES_A = f"""
AIが3つのお話をするよ。そのうち **2つは本当、1つだけウソ**！ どれがウソか当ててね。

1. すきなテーマと、むずかしさをえらんで「スタート」をおそう。
2. AIが3つのお話を出すよ。
3. 「これがウソだ！」と思うものを1つえらんで、ボタンをおそう。
4. 当たったら1ポイント！ AIが、どこがウソだったのかおしえてくれるよ。
5. {NUM_QUESTIONS}もんあそんで、なんポイントとれるかな？
"""

RULES_B = f"""
あなたが **本当の話かウソの話** を書いて、AIが当てようとするよ。**AIをだませたら、あなたの勝ち！**

1. 「本当の話」と「ウソの話」のどちらを書くか、こっそりえらぼう。
2. お話を書こう（{config.STORY_MIN_LEN}〜{config.STORY_MAX_LEN}文字）。
3. AIが「本当だと思う」か「ウソだと思う」か、理由といっしょに答えるよ。

**やくそく**：名前・住所・学校の名前など、自分や友だちのことが分かることは書かないでね。
だれかがいやな気持ちになるお話も書かないでね。

※ AIは人の心を読めるわけではありません。文章のようすから考えて当てようとしているだけです。
"""

TRUTH_CHOICES = [("本当の話", "true"), ("ウソの話", "lie")]


# --- ゲームAの画面処理 ---------------------------------------------------------
# 出力の順番：[state_a, question_md, choice_radio, result_md, score_md_a, answer_btn, next_btn]


def score_text_a(state):
    if state is None:
        return ""
    return f"**とくてん：{state['score']} ポイント**（{state['question_no']} / {NUM_QUESTIONS} もんめ）"


def render_question_a(state):
    """いまの問題を画面に表示するための値を作る（正解は表示しない）。"""

    quiz = state["current_quiz"]
    labels = [f"{i}. {s}" for i, s in enumerate(quiz["statements"], start=1)]

    question = (
        f"### だい {state['question_no']} もん（ぜんぶで {NUM_QUESTIONS} もん）\n"
        f"テーマ：**{state['theme']}**　／　むずかしさ：**{state['difficulty']}**\n\n"
        f"3つのうち、**ウソはどれかな？**"
    )

    return (
        state,
        question,
        gr.update(choices=labels, value=None, interactive=True),
        "",
        score_text_a(state),
        gr.update(interactive=True),
        gr.update(visible=False),
    )


def ui_start_a(theme, difficulty, state):
    try:
        new_state = next_question_a(new_state_a(theme, difficulty))
    except LLMError as e:
        return (state, f"⚠️ {e}", gr.update(), "", score_text_a(state), gr.update(), gr.update())

    return render_question_a(new_state)


def ui_answer_a(choice, state):
    no_change = gr.update()

    if state is None or state["current_quiz"] is None:
        return (state, no_change, no_change, "まずは「スタート」をおしてね。", no_change, no_change, no_change)

    if choice is None:
        return (state, no_change, no_change, "ウソだと思うものを1つえらんでね。", no_change, no_change, no_change)

    state, result = answer_a(state, choice)

    if result is None:  # すでに答えた問題（ボタンの連打など）
        return (state, no_change, no_change, no_change, no_change, no_change, no_change)

    mark = "⭕ せいかい！" if result["is_correct"] else "❌ ざんねん！"
    text = (
        f"## {mark}\n"
        f"ウソは **{result['lie_index'] + 1}. {result['lie_statement']}** でした。\n\n"
        f"💡 {result['explanation']}"
    )

    next_label = "けっかを見る" if state["finished"] else "つぎのもんだいへ"

    return (
        state,
        no_change,
        gr.update(interactive=False),
        text,
        score_text_a(state),
        gr.update(interactive=False),
        gr.update(visible=True, value=next_label),
    )


def ui_next_a(state):
    no_change = gr.update()

    if state is None:
        return (state, "まずは「スタート」をおしてね。", no_change, "", "", no_change, gr.update(visible=False))

    if state["finished"]:
        summary = (
            f"## おしまい！\n"
            f"### {NUM_QUESTIONS} もん中 {state['score']} もん せいかい！\n"
            f"{final_message_a(state['score'])}\n\n"
            f"もう一度あそぶときは、テーマをえらんで「スタート」をおしてね。"
        )
        return (
            state,
            summary,
            gr.update(choices=[], value=None, interactive=False),
            "",
            score_text_a(state),
            gr.update(interactive=False),
            gr.update(visible=False),
        )

    try:
        state = next_question_a(state)
    except LLMError as e:
        return (state, no_change, no_change, f"⚠️ {e}", no_change, no_change, no_change)

    return render_question_a(state)


# --- ゲームBの画面処理 ---------------------------------------------------------
# 出力の順番：[state_b, story_box, result_md_b, score_md_b]


def score_text_b(state):
    if state is None or state["rounds"] == 0:
        return ""
    ai_wins = state["rounds"] - state["player_wins"]
    return f"**あなた {state['player_wins']} かち　／　AI {ai_wins} かち**"


def ui_judge_b(story, truth, state):
    no_change = gr.update()

    if state is None:
        state = new_state_b()

    if truth is None:
        return (state, no_change, "①で「本当の話」か「ウソの話」かを、こっそりえらんでね。", score_text_b(state))

    try:
        state, result = play_b(state, story, truth)
    except LLMError as e:
        return (state, no_change, f"⚠️ {e}", score_text_b(state))

    if not result["ok"]:
        return (state, no_change, f"✋ {result['message']}", score_text_b(state))

    verdict = "🎉 **AIをだませた！ あなたの勝ち！**" if result["player_wins"] else "🤖 **AIに当てられちゃった！**"

    text = (
        f"> {result['story']}\n\n"
        f"🤖 AIのよそう：**{TRUTH_LABELS[result['ai_guess']]}だと思う！**\n\n"
        f"💬 {result['reason']}\n\n"
        f"✅ せいかいは… **{TRUTH_LABELS[result['truth']]}** でした！\n\n"
        f"## {verdict}"
    )

    return (state, gr.update(value=""), text, score_text_b(state))


# --- 画面の組み立て ------------------------------------------------------------


def build_demo():
    """Gradioの画面（gr.Blocks）を組み立てて返す。"""

    with gr.Blocks(title="AIウソ発見ゲーム") as demo:
        gr.Markdown("# 🕵️ AIウソ発見ゲーム")

        state_a = gr.State(None)
        state_b = gr.State(None)

        # ---------------- ゲームA ----------------
        with gr.Tab("ゲームA：AIのウソをみやぶれ！"):
            with gr.Accordion("あそびかた", open=False):
                gr.Markdown(RULES_A)

            with gr.Row():
                theme_dd = gr.Dropdown(config.THEMES, value=config.THEMES[0], label="テーマ")
                diff_radio = gr.Radio(list(config.DIFFICULTIES), value="ふつう", label="むずかしさ")

            start_btn = gr.Button("スタート", variant="primary")

            question_md = gr.Markdown("テーマとむずかしさをえらんで、「スタート」をおしてね。")
            choice_radio = gr.Radio(
                choices=[],
                type="index",
                label="ウソだと思うものをえらんでね",
                interactive=False,
            )
            answer_btn = gr.Button("これがウソだ！", interactive=False)
            result_md = gr.Markdown()
            next_btn = gr.Button("つぎのもんだいへ", visible=False)
            score_md_a = gr.Markdown()

            outputs_a = [state_a, question_md, choice_radio, result_md, score_md_a, answer_btn, next_btn]

            start_btn.click(ui_start_a, inputs=[theme_dd, diff_radio, state_a], outputs=outputs_a)
            answer_btn.click(ui_answer_a, inputs=[choice_radio, state_a], outputs=outputs_a)
            next_btn.click(ui_next_a, inputs=[state_a], outputs=outputs_a)

        # ---------------- ゲームB ----------------
        with gr.Tab("ゲームB：AIをだませるかな？"):
            with gr.Accordion("あそびかた", open=False):
                gr.Markdown(RULES_B)

            truth_radio = gr.Radio(TRUTH_CHOICES, label="① こっそりえらぼう：これから書くのは…")
            story_box = gr.Textbox(
                label="② お話を書こう",
                placeholder="れい：きのう、カレーを3ばいおかわりした",
                lines=3,
                max_lines=6,
            )
            judge_btn = gr.Button("AIに当ててもらう！", variant="primary")
            result_md_b = gr.Markdown()
            score_md_b = gr.Markdown()

            judge_btn.click(
                ui_judge_b,
                inputs=[story_box, truth_radio, state_b],
                outputs=[state_b, story_box, result_md_b, score_md_b],
            )

    return demo
