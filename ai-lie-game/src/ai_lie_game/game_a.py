"""ゲームA「AIのウソをみやぶれ！」の処理（Colabのセル4と6の前半に相当）。

状態（スコア・問題番号・現在の正解など）は gr.State に入れて使う。
gr.State の中身はサーバー側だけに保存され、参加者のブラウザには送られないため、
正解が見えてしまうことはない。また、参加者ごとに別々に保存される。
"""

import random

from ai_lie_game import config
from ai_lie_game.llm import call_llm
from ai_lie_game.prompts import QUIZ_SYSTEM_PROMPT, QUIZ_USER_TEMPLATE


def validate_quiz(data):
    """AIが返した問題データの形を検査し、整えた辞書を返す。おかしければ例外を出す。"""

    statements = data["statements"]
    if not isinstance(statements, list) or len(statements) != 3:
        raise ValueError("statements が3つではありません")

    statements = [str(s).strip() for s in statements]
    if any(not s for s in statements):
        raise ValueError("空の文があります")

    lie_index = int(data["lie_index"])
    if lie_index not in (0, 1, 2):
        raise ValueError(f"lie_index が範囲外です: {lie_index}")

    explanation = str(data["explanation"]).strip()
    if not explanation:
        raise ValueError("explanation が空です")

    return {"statements": statements, "lie_index": lie_index, "explanation": explanation}


def generate_quiz(theme, difficulty, avoid=None):
    """
    テーマとむずかしさを指定して、1問（3つの文＋正解＋解説）を作る。
    戻り値の lie_index（正解）はサーバー側だけで保持し、画面には出さない。
    """

    difficulty_desc = config.DIFFICULTIES.get(difficulty, config.DIFFICULTIES["ふつう"])
    avoid_list = "\n".join(f"- {s}" for s in avoid) if avoid else "（なし）"

    user_prompt = QUIZ_USER_TEMPLATE.format(
        theme=theme,
        difficulty_desc=difficulty_desc,
        avoid_list=avoid_list,
    )

    data = call_llm(QUIZ_SYSTEM_PROMPT, user_prompt, validator=validate_quiz)

    # AIはウソを特定の位置に置きがちなので、プログラム側で順番をシャッフルする
    order = random.sample(range(3), 3)
    statements = [data["statements"][i] for i in order]
    lie_index = order.index(data["lie_index"])

    return {
        "theme": theme,
        "difficulty": difficulty,
        "statements": statements,
        "lie_index": lie_index,
        "explanation": data["explanation"],
    }


def check_answer(quiz, choice):
    """プレイヤーの選択（0, 1, 2）を採点する。"""

    is_correct = choice == quiz["lie_index"]

    return {
        "is_correct": is_correct,
        "choice": choice,
        "lie_index": quiz["lie_index"],
        "lie_statement": quiz["statements"][quiz["lie_index"]],
        "explanation": quiz["explanation"],
    }


# --- 状態管理 ------------------------------------------------------------------


def new_state_a(theme, difficulty):
    """ゲームAの新しい状態を作る（スタートボタンを押したとき）。"""

    return {
        "theme": theme,
        "difficulty": difficulty,
        "score": 0,  # せいかい数
        "question_no": 0,  # いま何問目か
        "current_quiz": None,  # いまの問題（正解を含む。画面には出さない）
        "answered": False,  # いまの問題に答えたか
        "used_statements": [],  # これまでに出した文（同じ問題のくり返し防止）
        "finished": False,  # 全問おわったか
    }


def next_question_a(state):
    """次の問題を作って状態を更新する。AIの呼び出しに失敗したときは状態を変えずに例外を出す。"""

    if state["question_no"] >= config.NUM_QUESTIONS:
        state["finished"] = True
        state["current_quiz"] = None
        return state

    quiz = generate_quiz(
        state["theme"],
        state["difficulty"],
        avoid=state["used_statements"][-config.AVOID_HISTORY :],
    )

    state["current_quiz"] = quiz
    state["question_no"] += 1
    state["answered"] = False
    state["used_statements"].extend(quiz["statements"])

    return state


def answer_a(state, choice):
    """
    プレイヤーの答えを採点して状態を更新する。
    戻り値：(状態, 採点結果)。答えられない状況なら採点結果は None。
    """

    if state is None or state["current_quiz"] is None or state["answered"]:
        return state, None

    result = check_answer(state["current_quiz"], choice)

    if result["is_correct"]:
        state["score"] += 1

    state["answered"] = True

    if state["question_no"] >= config.NUM_QUESTIONS:
        state["finished"] = True

    return state, result


def final_message_a(score):
    """最後に表示するひとこと。"""

    if score == config.NUM_QUESTIONS:
        return "🏆 パーフェクト！ きみは ウソはっけん めいじんだ！"
    if score >= config.NUM_QUESTIONS * 0.6:
        return "🎉 すごい！ AIのウソを たくさん みやぶったね！"
    if score >= 1:
        return "👍 おしい！ もう一回ちょうせんしてみよう！"
    return "🌱 AIのウソは手ごわかったね。つぎは きっとできるよ！"
