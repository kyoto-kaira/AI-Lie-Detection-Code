"""ゲームA「AIのウソをみやぶれ！」の処理（Colabのセル4と6の前半に相当）。

状態（スコア・問題番号・現在の正解など）は gr.State に入れて使う。
gr.State の中身はサーバー側だけに保存され、参加者のブラウザには送られないため、
正解が見えてしまうことはない。また、参加者ごとに別々に保存される。

問題ができるまでの流れ：
  1. AIに問題を作らせる（generate_quiz → call_llm）
  2. プログラムで、3つの文が似すぎていないか・前の問題と同じでないかを調べる（find_quality_problems）
  3. AI自身に、事実や解説がまちがっていないかを見直させる（review_quiz）
  4. 2か3で問題が見つかったら、その理由をAIに伝えて作り直す（最大 config.QUIZ_MAX_ATTEMPTS 回）

待ち時間を短くするしくみ（先読み）：
  問題を画面に出したらすぐ、参加者が考えている間に、裏で次の問題づくり（1〜4）を始める（start_prefetch_a）。
  「つぎのもんだいへ」を押したときに、できあがっていればすぐ表示し、まだならできあがるまで待つ。
  次の問題は参加者の答えに左右されないので、先に作っても公平性は変わらない。
  先読みした問題の正解も、サーバーの中だけで保持し、画面には出さない。
"""

import json
import random
import threading
import time
import uuid
from concurrent.futures import CancelledError, ThreadPoolExecutor

from ai_lie_game import config
from ai_lie_game.llm import LLMError, call_llm
from ai_lie_game.prompts import (
    QUIZ_FEEDBACK_TEMPLATE,
    QUIZ_SYSTEM_PROMPT,
    QUIZ_USER_TEMPLATE,
    REVIEW_SYSTEM_PROMPT,
    REVIEW_USER_TEMPLATE,
)
from ai_lie_game.text_utils import normalize_for_compare, similarity

# 先読み用：裏で問題を作るスレッドと、ゲームごとの先読みの予約
_prefetch_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="quiz-prefetch")
_prefetch_jobs = {}  # game_id -> (何問目の問題か, Future)
_prefetch_lock = threading.Lock()
_MAX_PREFETCH_JOBS = 50  # ブラウザを閉じたまま放置されたゲームの分が、たまりすぎないようにする


def log_timing(message):
    """処理時間をターミナルに表示する（config.TIMING_LOG が True のときだけ）。"""

    if config.TIMING_LOG:
        print(f"[timing] {message}", flush=True)


def _get_three_texts(data, key):
    """data[key] が「空でない文字列3つのリスト」であることを確かめて返す。"""

    items = data.get(key)
    if not isinstance(items, list) or len(items) != 3:
        raise ValueError(f"{key} が3つではありません")

    items = [str(s).strip() for s in items]
    if any(not s for s in items):
        raise ValueError(f"{key} に空のものがあります")

    return items


def validate_quiz(data):
    """AIが返した問題データの形を検査し、整えた辞書を返す。おかしければ例外を出す。"""

    statements = _get_three_texts(data, "statements")

    try:
        lie_index = int(data.get("lie_index"))
    except (TypeError, ValueError):
        raise ValueError(f"lie_index が数字ではありません: {data.get('lie_index')}") from None
    if lie_index not in (0, 1, 2):
        raise ValueError(f"lie_index が範囲外です: {lie_index}")

    subjects = _get_three_texts(data, "subjects")
    notes = _get_three_texts(data, "notes")
    hint = str(data.get("hint") or "").strip()

    # 解説は、ウソの文の notes を使う（AIに同じ内容を2回書かせないことで、問題づくりを速くする）。
    # AIが explanation を書いてきた場合は、そちらを使う
    explanation = str(data.get("explanation") or "").strip() or notes[lie_index]

    return {
        "statements": statements,
        "subjects": subjects,
        "notes": notes,
        "lie_index": lie_index,
        "explanation": explanation,
        "hint": hint,
    }


def find_quality_problems(data, avoid=None):
    """
    問題の品質をプログラムで調べ、見つかった問題点（子どもには見せない、AIへの伝言）のリストを返す。
    問題がなければ空のリスト。
    """

    problems = []
    statements = data["statements"]
    subjects = [normalize_for_compare(s) for s in data["subjects"]]

    # 同じ対象（例：3つともキリン）をあつかっていないか
    for i in range(3):
        for j in range(i + 1, 3):
            a, b = subjects[i], subjects[j]
            if a and b and (a == b or a in b or b in a):
                problems.append(
                    f"{i + 1}番目と{j + 1}番目の文が、同じ対象（{data['subjects'][i]}）をあつかっています。"
                    "3つの文はそれぞれ別の対象にしてください。"
                )

    # 数字や単語を入れかえただけの、よく似た文になっていないか
    for i in range(3):
        for j in range(i + 1, 3):
            if similarity(statements[i], statements[j]) >= config.SIMILARITY_THRESHOLD:
                problems.append(
                    f"{i + 1}番目と{j + 1}番目の文がよく似ています。"
                    "数字や単語を入れかえただけの文ではなく、内容のちがう文にしてください。"
                )

    # 前に出した文と、ほとんど同じ文がないか
    for s in statements:
        for old in avoid or []:
            if similarity(s, old) >= config.DUPLICATE_THRESHOLD:
                problems.append(f"「{s}」は、前に出した「{old}」とほとんど同じです。別の内容にしてください。")
                break

    return problems


def validate_review(data):
    """AIの見直し結果の形を検査して、整えた辞書を返す。"""

    ok = data.get("ok")
    if isinstance(ok, str):
        ok = ok.strip().lower() == "true"
    if not isinstance(ok, bool):
        raise ValueError(f"ok の値が不正です: {ok}")

    problems = data.get("problems") or []
    if not isinstance(problems, list):
        problems = [problems]
    problems = [str(p).strip() for p in problems if str(p).strip()]

    if not ok and not problems:
        problems = ["見直しで問題ありと判断されました（理由の記載なし）"]

    return {"ok": ok, "problems": problems}


def review_quiz(data):
    """
    AI自身に問題を見直させる。
    戻り値：問題点のリスト（問題がなければ空のリスト）。見直しのAPI呼び出しに失敗したときは None。
    """

    quiz_json = json.dumps(
        {k: data[k] for k in ("statements", "lie_index", "notes")},
        ensure_ascii=False,
    )
    user_prompt = REVIEW_USER_TEMPLATE.format(quiz_json=quiz_json)

    try:
        review = call_llm(REVIEW_SYSTEM_PROMPT, user_prompt, validator=validate_review)
    except LLMError as e:
        # 見直しができなくても、問題自体はできているのでゲームは止めない
        print(f"[review_quiz] 見直しに失敗したため、見直しなしで出題します: {e}")
        return None

    return [] if review["ok"] else review["problems"]


def build_quiz_prompt(theme, difficulty, avoid=None, feedback=None):
    """出題用の指示文（ユーザー側）を組み立てる。"""

    difficulty_desc = config.DIFFICULTIES.get(difficulty, config.DIFFICULTIES["ふつう"])
    avoid_list = "\n".join(f"- {s}" for s in avoid) if avoid else "（なし）"
    feedback_text = (
        QUIZ_FEEDBACK_TEMPLATE.format(problems="\n".join(f"- {p}" for p in feedback)) if feedback else ""
    )

    return QUIZ_USER_TEMPLATE.format(
        theme=theme,
        difficulty_desc=difficulty_desc,
        avoid_list=avoid_list,
        feedback=feedback_text,
    )


def generate_quiz(theme, difficulty, avoid=None):
    """
    テーマとむずかしさを指定して、1問（3つの文＋正解＋解説）を作る。
    品質チェックに通らなければ、理由をAIに伝えて作り直す。
    戻り値の lie_index（正解）はサーバー側だけで保持し、画面には出さない。
    """

    avoid = list(avoid or [])
    feedback = []
    data = None
    problems = []

    # 処理時間の記録（どこに時間がかかっているかを調べるため）
    started = time.perf_counter()
    timing = {"generate_s": [], "review_s": [], "check_ms": []}

    for attempt in range(1, config.QUIZ_MAX_ATTEMPTS + 1):
        user_prompt = build_quiz_prompt(theme, difficulty, avoid, feedback)

        t = time.perf_counter()
        data = call_llm(QUIZ_SYSTEM_PROMPT, user_prompt, validator=validate_quiz)
        timing["generate_s"].append(round(time.perf_counter() - t, 2))

        # まずはお金のかからないプログラムのチェック。通ったときだけAIの見直しをする
        t = time.perf_counter()
        problems = find_quality_problems(data, avoid)
        timing["check_ms"].append(round((time.perf_counter() - t) * 1000, 1))

        if not problems and config.QUIZ_REVIEW_ENABLED:
            t = time.perf_counter()
            problems = review_quiz(data) or []
            timing["review_s"].append(round(time.perf_counter() - t, 2))

        if not problems:
            break

        print(f"[generate_quiz] 作り直し {attempt}/{config.QUIZ_MAX_ATTEMPTS}: {problems}")
        feedback = problems

    timing["attempts"] = attempt
    timing["total_s"] = round(time.perf_counter() - started, 2)
    log_timing(
        f"問題づくり 合計 {timing['total_s']}秒（{attempt}回作成）"
        f"　作成: {timing['generate_s']}秒　見直し: {timing['review_s']}秒　チェック: {timing['check_ms']}ミリ秒"
    )

    # AIはウソを特定の位置に置きがちなので、プログラム側で順番をシャッフルする
    order = random.sample(range(3), 3)

    return {
        "theme": theme,
        "difficulty": difficulty,
        "statements": [data["statements"][i] for i in order],
        "subjects": [data["subjects"][i] for i in order],
        "notes": [data["notes"][i] for i in order],
        "lie_index": order.index(data["lie_index"]),
        "explanation": data["explanation"],
        "hint": data["hint"],
        # 作り直しの上限までにチェックを通らなかった場合は False（画面に注意書きを出す）
        "checked": not problems,
        "timing": timing,
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
        "statements": quiz["statements"],
        "notes": quiz.get("notes") or [],
        "hint": quiz.get("hint", ""),
        "checked": quiz.get("checked", True),
    }


# --- 状態管理 ------------------------------------------------------------------


def new_state_a(theme, difficulty, previous=None):
    """
    ゲームAの新しい状態を作る（スタートボタンを押したとき）。
    previous に前のゲームの状態を渡すと、そのとき出した文を引きつぎ、ゲームをまたいだ同じ問題を防ぐ。
    """

    used = []
    if previous:
        used = list(previous.get("used_statements", []))[-config.AVOID_HISTORY :]
        cancel_prefetch_a(previous)  # 前のゲームの先読みは使わない

    return {
        "game_id": uuid.uuid4().hex,  # 先読みした問題を、このゲームと結びつけるための番号
        "theme": theme,
        "difficulty": difficulty,
        "score": 0,  # せいかい数
        "question_no": 0,  # いま何問目か
        "current_quiz": None,  # いまの問題（正解を含む。画面には出さない）
        "answered": False,  # いまの問題に答えたか
        "used_statements": used,  # これまでに出した文（同じ問題のくり返し防止）
        "history": [],  # 答えた問題の記録（ゲーム終了後のふりかえりに使う）
        "finished": False,  # 全問おわったか
    }


# --- 先読み --------------------------------------------------------------------


def start_prefetch_a(state):
    """
    いまの問題を表示したらすぐ、裏で次の問題を作りはじめる。
    すでに作りはじめている・最後の問題・先読みオフのときは何もしない。
    戻り値：新しく先読みを始めたら True。
    """

    if not config.PREFETCH_ENABLED or not state or state.get("finished") or not state.get("game_id"):
        return False

    next_no = state["question_no"] + 1
    if next_no > config.NUM_QUESTIONS:
        return False

    game_id = state["game_id"]
    # 次の問題では、いまの問題の文もふくめて、同じ内容を避ける
    args = (state["theme"], state["difficulty"], list(state["used_statements"][-config.AVOID_HISTORY :]))

    with _prefetch_lock:
        job = _prefetch_jobs.get(game_id)
        if job and job[0] == next_no:
            return False
        if job:
            job[1].cancel()

        _prefetch_jobs.pop(game_id, None)
        _prefetch_jobs[game_id] = (next_no, _prefetch_executor.submit(generate_quiz, *args))

        while len(_prefetch_jobs) > _MAX_PREFETCH_JOBS:
            oldest = next(iter(_prefetch_jobs))
            _prefetch_jobs.pop(oldest)[1].cancel()

    return True


def cancel_prefetch_a(state):
    """先読みを取り消す（新しいゲームを始めたときなど）。作りかけのものは、できあがっても使わない。"""

    if not state or not state.get("game_id"):
        return
    with _prefetch_lock:
        job = _prefetch_jobs.pop(state["game_id"], None)
    if job:
        job[1].cancel()


def _take_prefetched(state):
    """
    先読みした次の問題を受け取る（まだできていなければ、できあがるまで待つ）。
    戻り値：(問題 または None, 先読みの結果を表す文字列)
    """

    if not state.get("game_id"):
        return None, "なし"

    with _prefetch_lock:
        job = _prefetch_jobs.pop(state["game_id"], None)
    if job is None:
        return None, "なし"

    question_no, future = job
    if question_no != state["question_no"] + 1:
        future.cancel()
        return None, "なし"

    already_done = future.done()
    t = time.perf_counter()
    try:
        quiz = future.result()
    except (Exception, CancelledError) as e:
        # 先読みに失敗したときは、その場でもう一度作る
        print(f"[prefetch] 先読みに失敗したので、その場で作り直します: {type(e).__name__}: {e}")
        return None, "失敗"

    if already_done:
        return quiz, "間に合った"
    return quiz, f"作成中だった（残り {time.perf_counter() - t:.1f}秒 待った）"


def next_question_a(state):
    """次の問題を作って状態を更新する。AIの呼び出しに失敗したときは状態を変えずに例外を出す。"""

    if state["question_no"] >= config.NUM_QUESTIONS:
        state["finished"] = True
        state["current_quiz"] = None
        return state

    started = time.perf_counter()

    quiz, prefetch = _take_prefetched(state)
    if quiz is None:
        quiz = generate_quiz(
            state["theme"],
            state["difficulty"],
            avoid=state["used_statements"][-config.AVOID_HISTORY :],
        )

    log_timing(
        f"だい{state['question_no'] + 1}もん の準備 {time.perf_counter() - started:.2f}秒（先読み：{prefetch}）"
    )

    state["prefetch_status"] = prefetch
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

    quiz = state["current_quiz"]
    result = check_answer(quiz, choice)

    if result["is_correct"]:
        state["score"] += 1

    state["answered"] = True
    state.setdefault("history", []).append(
        {
            "question_no": state["question_no"],
            "statements": quiz["statements"],
            "notes": quiz.get("notes") or [],
            "lie_index": quiz["lie_index"],
            "choice": choice,
            "is_correct": result["is_correct"],
            "hint": quiz.get("hint", ""),
        }
    )

    if state["question_no"] >= config.NUM_QUESTIONS:
        state["finished"] = True

    return state, result


def summary_a(state):
    """
    ゲーム終了後のふりかえり用のデータを作る（AIは呼ばないので、お金はかからない）。
    record は、今後ランキング機能を追加するときに、そのまま保存できる形にしている。
    """

    history = state.get("history", [])
    total = len(history)
    score = state["score"]

    # まちがえた問題：本当の話をウソだと思ってしまったもの
    mistakes = []
    for h in history:
        if h["is_correct"]:
            continue
        notes = h.get("notes") or []
        mistakes.append(
            {
                "question_no": h["question_no"],
                "picked_statement": h["statements"][h["choice"]],
                "picked_note": notes[h["choice"]] if len(notes) == 3 else "",
                "lie_statement": h["statements"][h["lie_index"]],
            }
        )

    # 学んだポイント：各問題のヒント（同じものは1回だけ）
    hints = []
    for h in history:
        hint = h.get("hint", "")
        if hint and hint not in hints:
            hints.append(hint)

    return {
        "record": {
            "game": "A",
            "theme": state["theme"],
            "difficulty": state["difficulty"],
            "score": score,
            "total": total,
            "accuracy": round(score / total, 3) if total else 0.0,
        },
        "mistakes": mistakes,
        "hints": hints,
    }


def final_message_a(score):
    """最後に表示するひとこと。"""

    if score == config.NUM_QUESTIONS:
        return "🏆 パーフェクト！ きみは ウソはっけん めいじんだ！"
    if score >= config.NUM_QUESTIONS * 0.6:
        return "🎉 すごい！ AIのウソを たくさん みやぶったね！"
    if score >= 1:
        return "👍 おしい！ もう一回ちょうせんしてみよう！"
    return "🌱 AIのウソは手ごわかったね。つぎは きっとできるよ！"
