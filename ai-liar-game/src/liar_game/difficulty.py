"""難易度ごとの設定（質問回数・ヒント・スコア・AIの追い詰められ方）。

事件データそのものは cases.py に固定で定義されています。
ここでは「同じ仕組みを難易度でどう変えるか」だけを決めます。
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Difficulty:
    key: str
    label: str
    description: str
    max_questions: int  # 取り調べで使える質問の総数
    max_hints: int  # 助手に聞けるヒントの回数
    base_score: int  # 正解したときの基本点
    question_bonus: int  # 残り質問1回あたりのボーナス
    hint_penalty: int  # ヒント1回あたりの減点
    pressure_rule: str  # 嘘つきAIが証拠を突きつけられたときの振る舞い


DIFFICULTIES: dict[str, Difficulty] = {
    "easy": Difficulty(
        key="easy",
        label="やさしい",
        description="証拠は最初から全部そろっています。嘘は1つだけ。証拠を突きつけると動揺します。",
        max_questions=15,
        max_hints=3,
        base_score=100,
        question_bonus=5,
        hint_penalty=10,
        pressure_rule=(
            "・証拠や矛盾を具体的に突きつけられたら、動揺して、嘘をついていたことを素直に認めてください。\n"
            "・認めるのは、設定された「本当の行動」の範囲だけです。"
        ),
    ),
    "normal": Difficulty(
        key="normal",
        label="ふつう",
        description="証拠は調べるほど増えます。嘘を補強する嘘もあり、うっかり本音が漏れることがあります。",
        max_questions=12,
        max_hints=2,
        base_score=200,
        question_bonus=10,
        hint_penalty=30,
        pressure_rule=(
            "・証拠や矛盾を突きつけられたら、動揺しつつも、まずは言い訳やごまかしで切り抜けようとしてください。\n"
            "・同じ矛盾を2回以上、具体的な証拠つきで追及されたときだけ、少しずつ認めてください。\n"
            "・認めるのは、設定された「本当の行動」の範囲だけです。"
        ),
    ),
    "hard": Difficulty(
        key="hard",
        label="むずかしい",
        description="容疑者は4人。無実の人も秘密を隠します。嘘は連鎖し、証拠は探偵らしい行動でしか見つかりません。",
        max_questions=14,
        max_hints=1,
        base_score=300,
        question_bonus=10,
        hint_penalty=60,
        pressure_rule=(
            "・証拠や矛盾を突きつけられても、簡単には認めないでください。\n"
            "・矛盾を指摘されたら、「勘違いだった」「記憶があいまい」など、設定済みの嘘と矛盾しない形で言い逃れをしてください。\n"
            "・自白は、複数の証拠を重ねて追い詰められたときだけにしてください。\n"
            "・認めるのは、設定された「本当の行動」の範囲だけです。"
        ),
    ),
}

DIFFICULTY_ORDER = ("easy", "normal", "hard")


def get_difficulty(key: str) -> Difficulty:
    if key not in DIFFICULTIES:
        raise ValueError(f"難易度は {', '.join(DIFFICULTY_ORDER)} のいずれかを指定してください。")
    return DIFFICULTIES[key]


def difficulty_choices() -> list[tuple[str, str]]:
    """Gradio の Radio 用 (表示名, 値) のリスト。"""
    return [(DIFFICULTIES[k].label, k) for k in DIFFICULTY_ORDER]
