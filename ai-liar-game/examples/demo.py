"""Gradioを使わず、ターミナルで1問だけ試すサンプル。

実行:  uv run python examples/demo.py
"""

from dotenv import load_dotenv

from liar_game.interrogation import InterrogationGame

load_dotenv()

# 難易度は "easy" / "normal" / "hard"
game = InterrogationGame("easy")
print("佐藤への質問：19時15分にはどこにいましたか？")
print("佐藤の回答：", game.ask("B", "19時15分にはどこにいましたか？"))
print(f"残り質問：{game.remaining_questions}回")
