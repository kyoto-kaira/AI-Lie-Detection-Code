"""ゲームB「AIをだませるかな？」の処理（Colabのセル5と6の後半に相当）。"""

import re
import unicodedata

from ai_lie_game import config
from ai_lie_game.llm import call_llm
from ai_lie_game.prompts import JUDGE_SYSTEM_PROMPT, JUDGE_USER_TEMPLATE

TRUTH_LABELS = {"true": "本当の話", "lie": "ウソの話"}

# 個人情報らしきものを、AIに送る前にプログラム側で止めるためのパターン
PHONE_PATTERN = re.compile(r"0\d{9,10}")  # 電話番号（ハイフン除去後）
EMAIL_PATTERN = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")  # メールアドレス
POSTAL_PATTERN = re.compile(r"\d{3}-\d{4}")  # 郵便番号


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

    compact = re.sub(r"[\s\-‐−]", "", text)
    if PHONE_PATTERN.search(compact) or EMAIL_PATTERN.search(text) or POSTAL_PATTERN.search(text):
        return False, "電話番号やメールアドレス、住所のようなことは書かないでね。", text

    return True, "", text


def validate_judge(data):
    """AIが返した推理データの形を検査し、整えた辞書を返す。"""

    is_appropriate = data["is_appropriate"]
    if isinstance(is_appropriate, str):
        is_appropriate = is_appropriate.strip().lower() == "true"

    guess = str(data["guess"]).strip().lower()
    if guess not in ("true", "lie"):
        raise ValueError(f"guess の値が不正です: {guess}")

    reason = str(data["reason"]).strip()
    if not reason:
        raise ValueError("reason が空です")

    return {"is_appropriate": bool(is_appropriate), "guess": guess, "reason": reason}


def judge_story(story):
    """
    お話が本当かウソかをAIに推理させる。
    ※ プレイヤーが選んだ「本当/ウソ」はAIには送らない（文章だけを送る）。
    """

    user_prompt = JUDGE_USER_TEMPLATE.format(story=story)
    return call_llm(JUDGE_SYSTEM_PROMPT, user_prompt, validator=validate_judge)


def check_result(judge, truth):
    """AIの推理と、プレイヤーがこっそり選んだ答え（'true' / 'lie'）を比べて勝敗を決める。"""

    ai_correct = judge["guess"] == truth

    return {
        "ai_guess": judge["guess"],
        "truth": truth,
        "ai_correct": ai_correct,
        "player_wins": not ai_correct,  # AIがまちがえたらプレイヤーの勝ち
        "reason": judge["reason"],
    }


# --- 状態管理 ------------------------------------------------------------------


def new_state_b():
    """ゲームBの新しい状態を作る。"""

    return {"rounds": 0, "player_wins": 0}


def play_b(state, story, truth):
    """
    ゲームBを1回あそぶ（入力チェック → AIの推理 → 勝敗判定 → 状態更新）。
    戻り値：(状態, 結果)。結果の 'ok' が False のときは、'message' を表示して書き直してもらう。
    """

    if state is None:
        state = new_state_b()

    ok, message, cleaned = precheck_story(story)
    if not ok:
        return state, {"ok": False, "message": message}

    judge = judge_story(cleaned)

    if not judge["is_appropriate"]:
        return state, {"ok": False, "message": judge["reason"]}

    outcome = check_result(judge, truth)

    state["rounds"] += 1
    if outcome["player_wins"]:
        state["player_wins"] += 1

    return state, {"ok": True, "story": cleaned, **outcome}
