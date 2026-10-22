"""ゲームAの待ち時間を、本物のAIで計測するスクリプト（先読みなし／ありを比べる）。

使い方（プロジェクト直下で）：
    uv run python scripts/bench_game_a.py
    uv run python scripts/bench_game_a.py --questions 4 --think 20 --mode both

  --questions : 1回のゲームで何問まで進めるか（2以上。1問目は「スタート」の待ち時間）
  --think     : 参加者が1問を読んで答えて解説を読むまでの時間（秒）を想定して、その間待つ
  --mode      : off（先読みなし）／ on（先読みあり）／ both（両方を順に計測）

※ OpenAI API を実際に呼ぶので、料金がかかります。
   1問あたり、見直しありで約2回（作り直しが起きると最大6回）の呼び出しです。
"""

import argparse
import statistics
import time

from ai_lie_game import config, game_a


def play(prefetch, questions, think, theme, difficulty):
    config.PREFETCH_ENABLED = prefetch
    label = "先読みあり" if prefetch else "先読みなし"
    print(f"\n===== {label}：{questions}問、1問あたり {think}秒 考える想定 =====")

    t = time.perf_counter()
    state = game_a.next_question_a(game_a.new_state_a(theme, difficulty))
    start_wait = time.perf_counter() - t
    if questions > 1:
        game_a.start_prefetch_a(state)
    print(f"だい1もん（スタート）: {start_wait:.2f}秒")

    waits = []
    for _ in range(questions - 1):
        time.sleep(think)  # 参加者が読んで、答えて、解説を読んでいる時間
        state, _ = game_a.answer_a(state, 0)
        t = time.perf_counter()
        state = game_a.next_question_a(state)
        waits.append(time.perf_counter() - t)
        if state["question_no"] < questions:  # 計測しない問題まで先読みして、料金をむだにしない
            game_a.start_prefetch_a(state)
        print(f"だい{state['question_no']}もん: {waits[-1]:.2f}秒（先読み：{state['prefetch_status']}）")

    game_a.cancel_prefetch_a(state)
    return start_wait, waits


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--questions", type=int, default=3)
    parser.add_argument("--think", type=float, default=15.0)
    parser.add_argument("--mode", choices=["off", "on", "both"], default="both")
    parser.add_argument("--theme", default=config.THEMES[0])
    parser.add_argument("--difficulty", default="ふつう")
    args = parser.parse_args()

    config.get_api_key()  # キーがなければここで止まる
    print(
        f"モデル：{config.MODEL_NAME}　考える量：{config.REASONING_EFFORT or '（指定なし）'}"
        f"　出力の上限：{config.MAX_TOKENS}　見直し：{'あり' if config.QUIZ_REVIEW_ENABLED else 'なし'}"
    )

    modes = {"off": [False], "on": [True], "both": [False, True]}[args.mode]
    results = {}
    for prefetch in modes:
        results[prefetch] = play(prefetch, max(args.questions, 2), args.think, args.theme, args.difficulty)

    print("\n===== まとめ（「つぎのもんだいへ」を押してから次の問題が出るまで） =====")
    for prefetch, (start_wait, waits) in results.items():
        label = "先読みあり" if prefetch else "先読みなし"
        print(
            f"{label}：平均 {statistics.mean(waits):.2f}秒　最大 {max(waits):.2f}秒"
            f"　（スタート時 {start_wait:.2f}秒）"
        )


if __name__ == "__main__":
    main()
