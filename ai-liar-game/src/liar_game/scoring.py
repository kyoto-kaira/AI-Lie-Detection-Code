"""スコア計算。"""

from .difficulty import Difficulty


def calc_score(
    difficulty: Difficulty,
    is_correct: bool,
    questions_used: int,
    hints_used: int,
) -> dict:
    """スコアと内訳を返す。

    正解のとき：基本点 + 残り質問数×ボーナス − ヒント回数×減点（0点未満にはならない）
    不正解のとき：0点
    """
    remaining = max(difficulty.max_questions - questions_used, 0)

    if not is_correct:
        return {
            "score": 0,
            "base": 0,
            "question_bonus": 0,
            "hint_penalty": 0,
            "remaining_questions": remaining,
        }

    bonus = remaining * difficulty.question_bonus
    penalty = hints_used * difficulty.hint_penalty
    return {
        "score": max(difficulty.base_score + bonus - penalty, 0),
        "base": difficulty.base_score,
        "question_bonus": bonus,
        "hint_penalty": penalty,
        "remaining_questions": remaining,
    }
