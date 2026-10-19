"""エントリーポイント。`uv run liar-game` で Gradio が起動します。"""

from dotenv import load_dotenv


def main() -> None:
    # .env に書いた OPENAI_API_KEY などを環境変数として読み込む
    load_dotenv()

    from .ui import build_app

    # inbrowser=True：起動したらブラウザを自動で開く
    build_app().launch(inbrowser=True)


if __name__ == "__main__":
    main()
