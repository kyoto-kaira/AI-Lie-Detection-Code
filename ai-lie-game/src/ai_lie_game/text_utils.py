"""ゲームA・Bで共通して使う、文章の処理（似ている度合いの計算、AIに送る前の整形など）。"""

import difflib
import re
import unicodedata

# 似ているかどうかを比べるときに無視する記号
_IGNORE_PATTERN = re.compile(r"[\s、。,.!?「」『』()・…~]")
# 数字は「どの数字か」を無視して比べる（数字だけ入れかえた文を見つけるため）
_NUMBER_PATTERN = re.compile(r"\d+(?:\.\d+)?")


def normalize_for_compare(text):
    """比較用に文を整える（全角・半角をそろえ、数字と記号のちがいを無視する）。"""

    text = unicodedata.normalize("NFKC", str(text or "")).lower()
    text = _NUMBER_PATTERN.sub("0", text)
    return _IGNORE_PATTERN.sub("", text)


def similarity(a, b):
    """2つの文がどれだけ似ているかを 0.0〜1.0 で返す（1.0 はまったく同じ）。"""

    na, nb = normalize_for_compare(a), normalize_for_compare(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def escape_tags(text):
    """
    プレイヤーの文をAIへの指示文に埋め込む前に、< と > を全角にする。
    お話の中に </story> などと書いて、指示文の区切りをこわされないようにするため。
    """

    return str(text).replace("<", "＜").replace(">", "＞")
