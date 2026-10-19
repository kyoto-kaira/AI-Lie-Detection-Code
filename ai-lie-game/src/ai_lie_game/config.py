"""設定値（Colabのセル1に相当）。

APIキーはコードに書かず、環境変数 OPENAI_API_KEY（または .env ファイル）から読み込む。
"""

import os

from dotenv import find_dotenv, load_dotenv

# 実行したフォルダ（プロジェクト直下）の .env があれば、環境変数として読み込む
load_dotenv(find_dotenv(usecwd=True))

# --- モデル・API呼び出しの設定 -------------------------------------------------
MODEL_NAME = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")  # 比較的低コストで利用できるモデル
MAX_TOKENS = 1024  # 1回の応答の最大トークン数
MAX_RETRIES = 3  # 失敗したときの最大試行回数

# --- ゲームA「AIのウソをみやぶれ！」 -------------------------------------------
NUM_QUESTIONS = 5  # 1回のゲームの問題数
AVOID_HISTORY = 15  # 直近に出した文をAIに伝え、同じ問題がくり返されないようにする

THEMES = [
    "どうぶつ",
    "うちゅう",
    "たべもの",
    "むし",
    "からだのふしぎ",
    "うみのいきもの",
    "しょくぶつ",
    "のりもの",
]

# むずかしさごとに、AIへ伝える出題方針
DIFFICULTIES = {
    "かんたん": "小学校低学年向け。ウソの文は、少し考えればすぐ分かる、はっきりしたまちがいにする。",
    "ふつう": "小学校高学年向け。ウソの文は、知識があれば見抜ける程度のまちがいにする。",
    "むずかしい": "中学生以上向け。ウソの文は、数字や細かい部分だけを変えた、本当らしいまちがいにする。",
}

# --- ゲームB「AIをだませるかな？」 ---------------------------------------------
STORY_MIN_LEN = 5  # お話の最小文字数
STORY_MAX_LEN = 200  # お話の最大文字数

# --- サーバー設定 --------------------------------------------------------------
# 共有URLは発行せず、自分のPCからのみアクセスする
SERVER_NAME = "127.0.0.1"
SERVER_PORT = 7860


def get_api_key():
    """環境変数（または .env）から OpenAI のAPIキーを取り出す。なければ分かりやすいエラーにする。"""

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-ここに"):
        raise RuntimeError(
            "APIキーが見つかりません。\n"
            "  1. .env.example を .env という名前でコピーする\n"
            "  2. .env の OPENAI_API_KEY= のあとに、自分のAPIキーを書く\n"
            "（または、環境変数 OPENAI_API_KEY を設定してください）"
        )
    return api_key
