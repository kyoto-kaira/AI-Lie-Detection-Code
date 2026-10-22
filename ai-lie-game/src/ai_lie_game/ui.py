"""画面（Gradio）（Colabのセル7に相当）。画面の組み立ては build_demo() にまとめている。"""

import time

import gradio as gr

from ai_lie_game import config
from ai_lie_game.game_a import (
    answer_a,
    final_message_a,
    log_timing,
    new_state_a,
    next_question_a,
    start_prefetch_a,
    summary_a,
)
from ai_lie_game.game_b import (
    CONFIDENCE_LABELS,
    TRUTH_LABELS,
    UNANSWERED_TEXT,
    answer_b,
    count_answered,
    new_state_b,
    start_round_b,
)
from ai_lie_game.llm import LLMError

NUM_QUESTIONS = config.NUM_QUESTIONS

RULES_A = f"""
AIが3つのお話をするよ。そのうち **2つは本当、1つだけウソ**！ どれがウソか当ててね。

1. すきなテーマと、むずかしさをえらんで「スタート」をおそう。
2. AIが3つのお話を出すよ。
3. 「これがウソだ！」と思うものを1つえらんで、ボタンをおそう。
4. 当たったら1ポイント！ AIが、3つのお話それぞれの本当のところと、見やぶるヒントをおしえてくれるよ。
5. {NUM_QUESTIONS}もんあそんだら、ふりかえりを見てみよう。

※ お話は、本当のものもウソのものも、ぜんぶAIが書いています。
AIは、まちがったことでも自然で自信のある言い方で書くことがあります。
"""

RULES_B = f"""
あなたが **本当の話かウソの話** を書くと、AI名探偵がしつもんしながら当てようとするよ。**AIをだませたら、あなたの勝ち！**

1. 「本当の話」と「ウソの話」のどちらを書くか、こっそりえらぼう。
2. お話を書こう（{config.STORY_MIN_LEN}〜{config.STORY_MAX_LEN}文字）。
3. AIが、お話についてしつもんするよ（さいだい{config.B_MAX_QUESTIONS}かい）。うまく答えて、AIをまどわせよう！
4. 答えにこまったら「わからない」でもいいよ。同じしつもんをもう一度するけど、
   {config.B_MAX_SKIPS}かいつづくと、AIはそこまでの話で判定するよ。
5. AIが「本当だと思う」か「ウソだと思う」か、理由といっしょに答えるよ。

**やくそく**：名前・住所・学校の名前など、自分や友だちのことが分かることは書かないでね。
だれかがいやな気持ちになるお話も書かないでね。

※ お話と答えは、AIの会社（OpenAI）に送られて、AIが読みます。
※ AIは人の心を読めるわけではありません。文章や答えのようすから考えて「推測」しているだけです。
"""

TRUTH_CHOICES = [("本当の話", "true"), ("ウソの話", "lie")]

# Markdownで特別な意味をもつ記号（AIやプレイヤーの文をそのまま表示するときに、ただの文字としてあつかう）
_MD_SPECIAL = set("\\`*_{}[]()#+-.!|<>~$")


def md_escape(text):
    """プレイヤーやAIの文を、Markdownの記号として解釈されないように表示する。"""

    return "".join("\\" + c if c in _MD_SPECIAL else c for c in str(text))


def md_quote(text):
    """複数行の文を、Markdownの引用（>）として表示する。"""

    return "\n".join(f"> {md_escape(line)}" if line.strip() else ">" for line in str(text).splitlines())


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
    started = time.perf_counter()
    try:
        # 前のゲームで出した文を引きついで、同じ問題が出ないようにする
        new_state = next_question_a(new_state_a(theme, difficulty, previous=state))
    except LLMError as e:
        return (state, f"⚠️ {e}", gr.update(), "", score_text_a(state), gr.update(), gr.update())

    start_prefetch_a(new_state)  # 参加者が考えている間に、次の問題を作りはじめる
    log_timing(f"「スタート」→ だい1もん表示まで {time.perf_counter() - started:.2f}秒")
    return render_question_a(new_state)


def result_text_a(result):
    """答えたあとに表示する、せいかい・ふせいかいと解説。"""

    mark = "⭕ せいかい！" if result["is_correct"] else "❌ ざんねん！"
    lines = [
        f"## {mark}",
        f"ウソは **{result['lie_index'] + 1}. {md_escape(result['lie_statement'])}** でした。",
        "",
        f"💡 {md_escape(result['explanation'])}",
    ]

    notes = result.get("notes") or []
    if len(notes) == 3:
        lines += ["", "#### 3つのお話の かいせつ"]
        for i, (statement, note) in enumerate(zip(result["statements"], notes)):
            label = "❌ **ウソ**" if i == result["lie_index"] else "✅ **本当**"
            picked = "　👈 あなたがえらんだもの" if i == result["choice"] else ""
            # ウソの文の解説は、すぐ上の 💡 と同じ文なら、くり返さない
            note_text = "" if note == result["explanation"] else f"  \n　{md_escape(note)}"
            lines.append(f"- {label}　{i + 1}. {md_escape(statement)}{picked}{note_text}")

    if result.get("hint"):
        lines += ["", f"🔍 **見やぶるヒント**：{md_escape(result['hint'])}"]

    if not result.get("checked", True):
        lines += [
            "",
            "⚠️ このもんだいは、AIが見直しても気になるところが残ったよ。"
            "解説がまちがっているかもしれないので、図鑑でもたしかめてみよう！",
        ]

    return "\n".join(lines)


def ui_answer_a(choice, state):
    no_change = gr.update()

    if state is None or state["current_quiz"] is None:
        return (state, no_change, no_change, "まずは「スタート」をおしてね。", no_change, no_change, no_change)

    if choice is None:
        return (state, no_change, no_change, "ウソだと思うものを1つえらんでね。", no_change, no_change, no_change)

    state, result = answer_a(state, choice)

    if result is None:  # すでに答えた問題（ボタンの連打など）
        return (state, no_change, no_change, no_change, no_change, no_change, no_change)

    # 念のため：先読みがまだ始まっていなければ、ここで始める（すでに始まっていれば何もしない）
    start_prefetch_a(state)

    next_label = "けっかを見る" if state["finished"] else "つぎのもんだいへ"

    return (
        state,
        no_change,
        gr.update(interactive=False),
        result_text_a(result),
        score_text_a(state),
        gr.update(interactive=False),
        gr.update(visible=True, value=next_label),
    )


def summary_text_a(state):
    """ゲーム終了後のふりかえり。"""

    summary = summary_a(state)
    record = summary["record"]
    percent = round(record["accuracy"] * 100)

    lines = [
        "## おしまい！",
        f"### {record['total']} もん中 {record['score']} もん せいかい！（せいかいりつ {percent}%）",
        final_message_a(record["score"]),
    ]

    if summary["mistakes"]:
        lines += [
            "",
            "#### 🔎 ふりかえり：本当なのに、ウソだと思ったお話",
            "びっくりするような本当の話は、ウソに見えやすいんだ。",
        ]
        for m in summary["mistakes"]:
            note = f"  \n　{md_escape(m['picked_note'])}" if m["picked_note"] else ""
            lines.append(f"- だい{m['question_no']}もん：{md_escape(m['picked_statement'])}{note}")

    if summary["hints"]:
        lines += ["", "#### 📝 きょう学んだ、ウソを見やぶるポイント"]
        lines += [f"- {md_escape(h)}" for h in summary["hints"]]

    lines += [
        "",
        "#### 🤖 AIについて",
        "きょうのお話は、本当の話もウソの話も、ぜんぶAIが書いたものだよ。"
        "AIは、まちがったことでも、自然で自信のある言い方で書くことがあるんだ。"
        "読みやすい文章だからといって正しいとは限らないから、気になったら図鑑や先生にたしかめよう！",
        "",
        "もう一度あそぶときは、テーマをえらんで「スタート」をおしてね。",
    ]

    return "\n".join(lines)


def ui_next_a(state):
    no_change = gr.update()

    if state is None:
        return (state, "まずは「スタート」をおしてね。", no_change, "", "", no_change, gr.update(visible=False))

    if state["finished"]:
        return (
            state,
            summary_text_a(state),
            gr.update(choices=[], value=None, interactive=False),
            "",
            score_text_a(state),
            gr.update(interactive=False),
            gr.update(visible=False),
        )

    started = time.perf_counter()
    try:
        state = next_question_a(state)
    except LLMError as e:
        return (state, no_change, no_change, f"⚠️ {e}", no_change, no_change, no_change)

    start_prefetch_a(state)  # 参加者が考えている間に、次の問題を作りはじめる
    log_timing(
        f"「つぎのもんだいへ」→ だい{state['question_no']}もん表示まで {time.perf_counter() - started:.2f}秒"
        f"（先読み：{state.get('prefetch_status', 'なし')}）"
    )
    return render_question_a(state)


# --- ゲームBの画面処理 ---------------------------------------------------------
# 出力の順番：
# [state_b, truth_radio, story_box, start_btn_b, convo_md, answer_box, answer_btn, skip_btn, reset_btn,
#  result_md_b, score_md_b]


def score_text_b(state):
    if state is None or state["rounds"] == 0:
        return ""
    ai_wins = state["rounds"] - state["player_wins"]
    return f"**あなた {state['player_wins']} かち　／　AI {ai_wins} かち**"


def conversation_text_b(story, turns, current_question=None, repeat=False, skips=0):
    """お話と、AIとのやりとりを表示する文を作る。"""

    asked = count_answered(turns)
    lines = ["#### 📖 あなたのお話", md_quote(story), "", "#### 🕵️ AI名探偵とのやりとり"]

    if not turns and not current_question:
        lines.append("（しつもんなし）")

    for t in turns:
        if t["answered"]:
            answer = md_escape(t["answer"])
        else:
            # 「わからない」など：回数には数えないことが分かるようにする
            answer = f"{md_escape(t['answer']) or UNANSWERED_TEXT}　*（かいすうには数えないよ）*"
        lines.append(f"🕵️ **AI**：{md_escape(t['question'])}  \n🙋 **あなた**：{answer}")

    if current_question:
        lines += ["", f"### 🕵️ しつもん（{asked + 1} / {config.B_MAX_QUESTIONS}）", md_escape(current_question)]
        if repeat:
            rest = config.B_MAX_SKIPS - skips
            lines.append(
                f"\n🤔 もういちど聞くね。（あと {rest} かい「わからない」がつづくと、AIがそこまでの話で判定するよ）"
            )

    return "\n\n".join(lines)


def judged_text_b(result):
    """AIの判定と勝敗。"""

    verdict = "🎉 **AIをだませた！ あなたの勝ち！**" if result["player_wins"] else "🤖 **AIに当てられちゃった！**"
    lines = [
        f"🤖 AIのよそう：**{TRUTH_LABELS[result['ai_guess']]}だと思う！**"
        f"（{CONFIDENCE_LABELS.get(result['confidence'], '')}）",
        "",
        f"💬 {md_escape(result['reason'])}",
    ]
    if result.get("clues"):
        lines += ["", "🔍 AIが手がかりにしたこと：" + "　／　".join(md_escape(c) for c in result["clues"])]
    lines += [
        "",
        f"✅ せいかいは… **{TRUTH_LABELS[result['truth']]}** でした！",
        "",
        f"## {verdict}",
        "",
        "※ AIの判定は、お話と答えのようすから考えた「推測」だよ。本当かどうかを確かめたわけではないんだ。",
        "",
        "もう一回あそぶときは、①と②からはじめてね。",
    ]
    return "\n".join(lines)


def render_b(state, convo="", result_text="", asking=False, clear_story=False):
    """ゲームBの画面全体の表示を、いまの状態に合わせて作る。"""

    idle = not asking
    return (
        state,
        gr.update(interactive=idle, value=None) if clear_story else gr.update(interactive=idle),
        gr.update(interactive=idle, value="") if clear_story else gr.update(interactive=idle),
        gr.update(visible=idle),
        convo,
        gr.update(visible=asking, value=""),
        gr.update(visible=asking),
        gr.update(visible=asking),
        gr.update(visible=asking),
        result_text,
        score_text_b(state),
    )


def _message_b(state, message):
    """入力のやり直しやエラーのとき：画面はそのままで、メッセージだけを出す。"""

    no_change = gr.update()
    return (state, no_change, no_change, no_change, no_change, no_change, no_change, no_change, no_change,
            message, score_text_b(state))  # fmt: skip


def _render_result_b(state, result):
    if not result["ok"]:
        return _message_b(state, f"✋ {result['message']}")

    rnd = state["round"]
    if result["phase"] == "asking":
        convo = conversation_text_b(rnd["story"], rnd["turns"], result["question"], result["repeat"], result["skips"])
        return render_b(state, convo, "", asking=True)

    convo = conversation_text_b(result["story"], result["turns"])
    return render_b(state, convo, judged_text_b(result), asking=False, clear_story=True)


def ui_start_b(truth, story, state):
    try:
        new_state, result = start_round_b(state, story, truth)
    except LLMError as e:
        return _message_b(state, f"⚠️ {e}")
    return _render_result_b(new_state, result)


def ui_answer_b(answer, state):
    try:
        new_state, result = answer_b(state, answer)
    except LLMError as e:
        return _message_b(state, f"⚠️ {e}")
    return _render_result_b(new_state, result)


def ui_skip_b(state):
    return ui_answer_b("わからない", state)


def ui_reset_b(state):
    """いまの勝負をやめて、お話を書くところにもどる（勝敗には数えない）。"""

    state = dict(state or new_state_b())
    state["phase"] = "idle"
    state["round"] = None
    return render_b(state, "", "いまの勝負はやめたよ。①と②からはじめてね。", asking=False, clear_story=True)


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
            start_btn_b = gr.Button("このお話で勝負！", variant="primary")

            convo_md = gr.Markdown()
            answer_box = gr.Textbox(
                label="③ しつもんに答えよう",
                placeholder="答えを書いて、Enterか「こたえる」をおしてね",
                visible=False,
            )
            with gr.Row():
                answer_btn_b = gr.Button("こたえる", variant="primary", visible=False)
                skip_btn = gr.Button("わからない", visible=False)
                reset_btn = gr.Button("べつのお話にする", visible=False)

            result_md_b = gr.Markdown()
            score_md_b = gr.Markdown()

            outputs_b = [
                state_b, truth_radio, story_box, start_btn_b, convo_md,
                answer_box, answer_btn_b, skip_btn, reset_btn, result_md_b, score_md_b,
            ]  # fmt: skip

            start_btn_b.click(ui_start_b, inputs=[truth_radio, story_box, state_b], outputs=outputs_b)
            answer_btn_b.click(ui_answer_b, inputs=[answer_box, state_b], outputs=outputs_b)
            answer_box.submit(ui_answer_b, inputs=[answer_box, state_b], outputs=outputs_b)
            skip_btn.click(ui_skip_b, inputs=[state_b], outputs=outputs_b)
            reset_btn.click(ui_reset_b, inputs=[state_b], outputs=outputs_b)

    return demo
