"""ゲームB「AIをだませるかな？」の処理（Colabのセル5と6の後半に相当）。

1回の勝負の流れ：
  1. プレイヤーが「本当の話」か「ウソの話」かをこっそり選び、お話を書く（start_round_b）
  2. AI（名探偵）が質問を1つする
  3. プレイヤーが答える（answer_b）。AIは答えを見て、次の質問をするか、判定するかを決める
     - 答えてもらえた質問が config.B_MAX_QUESTIONS 回になったら、必ず判定する
     - 「わからない」などの答えのときは、同じ質問をもう一度する（回数には数えない）
       config.B_MAX_SKIPS 回つづいたら、そこまでの会話で判定する
  4. AIの判定と、プレイヤーがこっそり選んだ答えを比べて勝敗を決める

※ プレイヤーが選んだ「本当/ウソ」はAIには送らない。AIの判定は、文章と答えからの「推測」にすぎない。
※ 各関数は、AIの呼び出しに失敗したときに元の状態をこわさないよう、状態のコピーを更新して返す。
"""

import copy
import re
import unicodedata

from ai_lie_game import config
from ai_lie_game.llm import call_llm
from ai_lie_game.prompts import DETECTIVE_SYSTEM_PROMPT, DETECTIVE_USER_TEMPLATE
from ai_lie_game.text_utils import escape_tags, similarity

TRUTH_LABELS = {"true": "本当の話", "lie": "ウソの話"}
CONFIDENCE_LABELS = {"high": "かなり自信あり", "medium": "どちらかといえば", "low": "あまり自信なし"}

# 個人情報らしきものを、AIに送る前にプログラム側で止めるためのパターン
PHONE_PATTERN = re.compile(r"0\d{9,10}")  # 電話番号（ハイフン除去後）
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")  # メールアドレス
POSTAL_PATTERN = re.compile(r"\d{3}-\d{4}")  # 郵便番号

# 「答えていない」とみなす答え（AIに送らずにプログラムで判断する。言い方がちがうものはAIが判断する）
SKIP_WORDS = [
    "わからない", "わかんない", "わかりません", "わからん",
    "分からない", "分かんない", "分かりません",
    "しらない", "しりません", "知らない", "知りません",
    "おぼえてない", "覚えてない", "わすれた", "忘れた",
    "パス", "ぱす", "pass", "ひみつ", "秘密",
    "いえない", "言えない", "こたえない", "答えない",
]  # fmt: skip
_SKIP_PATTERN = re.compile(
    r"^(?:うーん|えーと|えっと|んー)?"
    rf"(?:{'|'.join(map(re.escape, SKIP_WORDS))})"
    r"(?:です|でした|だよ|だ|かも|かな|な|よ|ね)*$"
)
_ANSWER_IGNORE_PATTERN = re.compile(r"[\s、。,.!?…~〜「」]")

UNANSWERED_TEXT = "（こたえなかった）"
SAME_QUESTION_THRESHOLD = 0.8  # 前の質問とこれ以上似ていたら、同じ質問とみなしてAIに作り直させる


# --- 入力チェック --------------------------------------------------------------


def _contains_personal_info(text):
    compact = re.sub(r"[\s\-‐−]", "", text)
    return bool(PHONE_PATTERN.search(compact) or EMAIL_PATTERN.search(text) or POSTAL_PATTERN.search(text))


def precheck_story(story):
    """
    AIに送る前の入力チェック。
    戻り値：(OKかどうか, 子ども向けのメッセージ, 整えたお話)
    """

    text = unicodedata.normalize("NFKC", story or "").strip()  # 全角数字などを半角にそろえる

    if len(text) < config.STORY_MIN_LEN:
        return False, f"お話がみじかすぎるよ。{config.STORY_MIN_LEN}文字いじょうで書いてね。", text

    if len(text) > config.STORY_MAX_LEN:
        return False, f"お話がながすぎるよ。{config.STORY_MAX_LEN}文字いないで書いてね。", text

    if _contains_personal_info(text):
        return False, "電話番号やメールアドレス、住所のようなことは書かないでね。", text

    return True, "", text


def is_skip_answer(text):
    """「わからない」「パス」や空欄など、質問に答えていない答えかどうか。"""

    core = _ANSWER_IGNORE_PATTERN.sub("", unicodedata.normalize("NFKC", text or "").lower())
    return core == "" or bool(_SKIP_PATTERN.match(core))


def precheck_answer(answer):
    """
    質問への答えを、AIに送る前にチェックする。
    戻り値：(状態, 子ども向けのメッセージ, 整えた答え)
      状態は "ok"（AIに送る）、"skip"（答えていない）、"ng"（書き直してもらう）のどれか。
    """

    text = unicodedata.normalize("NFKC", answer or "").strip()

    if is_skip_answer(text):
        return "skip", "", text

    if len(text) > config.ANSWER_MAX_LEN:
        return "ng", f"答えがながすぎるよ。{config.ANSWER_MAX_LEN}文字いないで書いてね。", text

    if _contains_personal_info(text):
        return "ng", "電話番号やメールアドレス、住所のようなことは書かないでね。", text

    return "ok", "", text


# --- AIとのやりとり ------------------------------------------------------------


def count_answered(turns):
    """答えてもらえた質問の数（「わからない」などは数えない）。"""

    return sum(1 for t in turns if t["answered"])


def format_conversation(turns):
    """これまでの質問と答えを、AIに送る形の文字列にする。"""

    if not turns:
        return "（まだありません）"

    lines = []
    for i, t in enumerate(turns, start=1):
        answer = t["answer"] if t["answered"] else f"{UNANSWERED_TEXT} {t['answer']}".strip()
        lines.append(f"Q{i}: {escape_tags(t['question'])}")
        lines.append(f"A{i}: {escape_tags(answer)}")
    return "\n".join(lines)


def make_step_validator(can_judge, must_judge, previous_questions, allow_unclear):
    """
    AIの応答（質問か判定）を検査する関数を作る。
    allow_unclear が True のとき、AIが「答えがはっきりしない」と言ったら、質問・判定の中身は検査しない
    （その場合、プログラムが同じ質問をもう一度するため、AIの次の質問や判定は使わない）。
    """

    def validate(data):
        is_appropriate = data.get("is_appropriate", True)
        if isinstance(is_appropriate, str):
            is_appropriate = is_appropriate.strip().lower() == "true"

        if not is_appropriate:
            message = str(data.get("message") or "").strip() or "そのお話や答えは、書き直してね。"
            return {"is_appropriate": False, "message": message}

        status = str(data.get("last_answer_status") or "answered").strip().lower()
        if status not in ("answered", "unclear", "none"):
            status = "answered"

        result = {"is_appropriate": True, "message": "", "last_answer_status": status}

        if status == "unclear" and allow_unclear:
            return {**result, "action": "unclear"}

        action = str(data.get("action") or "").strip().lower()
        if action not in ("ask", "judge"):
            raise ValueError(f"action の値が不正です: {action}")
        if must_judge and action != "judge":
            raise ValueError("判定しなければいけないのに、質問しようとしました")
        if not can_judge and action == "judge":
            raise ValueError("まだ判定できないのに、判定しようとしました")

        if action == "ask":
            question = str(data.get("question") or "").strip()
            if not question:
                raise ValueError("question が空です")
            if any(similarity(question, q) >= SAME_QUESTION_THRESHOLD for q in previous_questions):
                raise ValueError(f"前と同じ質問をしようとしました: {question}")
            return {**result, "action": "ask", "question": question}

        guess = str(data.get("guess") or "").strip().lower()
        if guess not in ("true", "lie"):
            raise ValueError(f"guess の値が不正です: {guess}")

        reason = str(data.get("reason") or "").strip()
        if not reason:
            raise ValueError("reason が空です")

        confidence = str(data.get("confidence") or "").strip().lower()
        if confidence not in CONFIDENCE_LABELS:
            confidence = "medium"

        clues = data.get("clues") or []
        if not isinstance(clues, list):
            clues = [clues]
        clues = [str(c).strip() for c in clues if str(c).strip()][:3]

        return {**result, "action": "judge", "guess": guess, "reason": reason,
                "confidence": confidence, "clues": clues}  # fmt: skip

    return validate


def ask_detective(story, turns, can_judge, must_judge, allow_unclear=True):
    """AI（名探偵）に、次の質問か判定を1回だけたずねる。"""

    user_prompt = DETECTIVE_USER_TEMPLATE.format(
        story=escape_tags(story),
        conversation=format_conversation(turns),
        asked=count_answered(turns),
        max_questions=config.B_MAX_QUESTIONS,
        can_judge=str(can_judge).lower(),
        must_judge=str(must_judge).lower(),
    )
    validator = make_step_validator(
        can_judge, must_judge, [t["question"] for t in turns], allow_unclear
    )
    return call_llm(DETECTIVE_SYSTEM_PROMPT, user_prompt, validator=validator)


def check_result(judge, truth):
    """AIの推理と、プレイヤーがこっそり選んだ答え（'true' / 'lie'）を比べて勝敗を決める。"""

    ai_correct = judge["guess"] == truth

    return {
        "ai_guess": judge["guess"],
        "truth": truth,
        "ai_correct": ai_correct,
        "player_wins": not ai_correct,  # AIがまちがえたらプレイヤーの勝ち
        "reason": judge["reason"],
        "confidence": judge.get("confidence", "medium"),
        "clues": judge.get("clues", []),
    }


# --- 状態管理 ------------------------------------------------------------------


def new_state_b():
    """ゲームBの新しい状態を作る。"""

    return {
        "rounds": 0,  # 勝負した回数（判定まで進んだものだけ）
        "player_wins": 0,  # プレイヤーが勝った回数
        "phase": "idle",  # "idle"（お話を書く前）/ "asking"（質問中）/ "judged"（判定ずみ）
        "round": None,  # いまの勝負（お話、こっそり選んだ答え、会話の記録など）
        "records": [],  # 勝負ごとの記録（今後ランキング機能を追加するときに使う）
    }


def _ensure_state(state):
    """古い形の状態や None を、新しい形の状態に直したコピーを返す。"""

    new = new_state_b()
    if state:
        new.update(copy.deepcopy(state))
    return new


def _asking(state, question, repeat=False):
    rnd = state["round"]
    rnd["question"] = question
    state["phase"] = "asking"
    return state, {
        "ok": True,
        "phase": "asking",
        "question": question,
        "repeat": repeat,  # 「わからない」のあとで、同じ質問をもう一度しているか
        "skips": rnd["skips"],
        "asked": count_answered(rnd["turns"]),
    }


def _finish(state, judge):
    """AIの判定で勝負を終わらせ、勝敗を記録する。"""

    rnd = state["round"]
    outcome = check_result(judge, rnd["truth"])

    state["rounds"] += 1
    if outcome["player_wins"]:
        state["player_wins"] += 1

    state["phase"] = "judged"
    rnd["question"] = None
    state["records"].append(
        {
            "game": "B",
            "player_wins": outcome["player_wins"],
            "questions_answered": count_answered(rnd["turns"]),
        }
    )

    return state, {
        "ok": True,
        "phase": "judged",
        "story": rnd["story"],
        "turns": copy.deepcopy(rnd["turns"]),
        **outcome,
    }


def _apply_step(state, step):
    if step["action"] == "judge":
        return _finish(state, step)
    return _asking(state, step["question"])


def start_round_b(state, story, truth):
    """
    新しい勝負を始める（入力チェック → AIの最初の質問）。
    戻り値：(状態, 結果)。結果の 'ok' が False のときは、'message' を表示して書き直してもらう。
    """

    original = state
    state = _ensure_state(state)

    if truth not in TRUTH_LABELS:
        return original, {"ok": False, "message": "①で「本当の話」か「ウソの話」かを、こっそりえらんでね。"}

    ok, message, cleaned = precheck_story(story)
    if not ok:
        return original, {"ok": False, "message": message}

    turns = []
    step = ask_detective(
        cleaned,
        turns,
        can_judge=config.B_MIN_QUESTIONS <= 0,
        must_judge=config.B_MAX_QUESTIONS <= 0,
        allow_unclear=False,
    )

    if not step["is_appropriate"]:
        return original, {"ok": False, "message": step["message"]}

    state["round"] = {"story": cleaned, "truth": truth, "turns": turns, "question": None, "skips": 0}
    return _apply_step(state, step)


def _skip(state, original, answer_text):
    """
    答えてもらえなかったときの処理。同じ質問をもう一度する。
    「わからない」などが config.B_MAX_SKIPS 回つづいたら、そこまでの会話で判定する。
    """

    rnd = state["round"]
    rnd["skips"] += 1
    rnd["turns"].append({"question": rnd["question"], "answer": answer_text, "answered": False})

    if rnd["skips"] < config.B_MAX_SKIPS:
        return _asking(state, rnd["question"], repeat=True)

    step = ask_detective(rnd["story"], rnd["turns"], can_judge=True, must_judge=True, allow_unclear=False)
    if not step["is_appropriate"]:
        return original, {"ok": False, "message": step["message"]}
    return _finish(state, step)


def answer_b(state, answer):
    """
    AIの質問に答える。
    戻り値：(状態, 結果)。結果の 'phase' が "asking" なら次の質問、"judged" なら判定結果。
    'ok' が False のときは、'message' を表示して書き直してもらう（状態は変わらない）。
    """

    if not state or state.get("phase") != "asking" or not state.get("round"):
        return state, {"ok": False, "message": "まずは、お話を書いて「このお話で勝負！」をおしてね。"}

    original = state
    state = _ensure_state(state)
    rnd = state["round"]

    status, message, cleaned = precheck_answer(answer)
    if status == "ng":
        return original, {"ok": False, "message": message}

    if status == "skip":
        return _skip(state, original, cleaned)

    # いったん答えを会話に加えて、AIに次の一手をたずねる
    turns = rnd["turns"] + [{"question": rnd["question"], "answer": cleaned, "answered": True}]
    answered = count_answered(turns)
    step = ask_detective(
        rnd["story"],
        turns,
        can_judge=answered >= config.B_MIN_QUESTIONS,
        must_judge=answered >= config.B_MAX_QUESTIONS,
        allow_unclear=True,
    )

    if not step["is_appropriate"]:
        return original, {"ok": False, "message": step["message"]}

    if step["action"] == "unclear":
        # AIが「質問に答えていない」と判断した答え：同じ質問をもう一度する
        return _skip(state, original, cleaned)

    rnd["turns"] = turns
    rnd["skips"] = 0
    return _apply_step(state, step)
