"""アプリの入口。`uv run ai-lie-game` で、この main() が呼ばれてGradioの画面が開く。"""

from ai_lie_game import config
from ai_lie_game.ui import build_demo


def main():
    # 起動前にAPIキーの有無を確認する（なければ、設定方法つきのエラーで止まる）
    try:
        config.get_api_key()
    except RuntimeError as e:
        raise SystemExit(f"⚠️ {e}") from None

    demo = build_demo()

    # 共有URLは発行せず、自分のPCからのみアクセスする
    demo.queue().launch(
        share=False,
        server_name=config.SERVER_NAME,
        server_port=config.SERVER_PORT,
        inbrowser=True,
    )


if __name__ == "__main__":
    main()
