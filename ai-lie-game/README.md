# 🕵️ AIウソ発見ゲーム

AIが出す3つのお話から「ウソ」を見破る **ゲームA**、自分で書いたお話でAIをだます **ゲームB** を遊べる、
Gradio製のブラウザゲームです。AIの出力が必ずしも正しくないことを、遊びながら体験できます。

- ゲームA：AIのウソをみやぶれ！（3つの文のうち1つだけがウソ。全5問）
- ゲームB：AIをだませるかな？（本当/ウソのお話を書いて、AIに当てさせる）

## 必要なもの

- [uv](https://docs.astral.sh/uv/)（Pythonの環境構築ツール。Python本体も自動で用意してくれます）
- OpenAIのAPIキー

uv のインストール（まだの人だけ）：

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## セットアップと起動

```bash
git clone <このリポジトリのURL>
cd ai-lie-game

# 1. APIキーを設定する（.env は GitHub に公開されません）
cp .env.example .env
#    .env をエディタで開き、OPENAI_API_KEY= のあとに自分のキーを書く

# 2. 起動（初回は必要なパッケージが自動でインストールされます）
uv run ai-lie-game
```

ブラウザが自動で開き、`http://127.0.0.1:7860` でゲームが遊べます。
自動で開かないときは、このURLを手動で開いてください。

> `uv run python -m ai_lie_game` でも同じように起動できます。

## テスト

APIは呼ばないので、キーなしで実行できます。

```bash
uv run pytest
```

## フォルダ構成

```
ai-lie-game/
├── pyproject.toml        # 依存パッケージ・コマンド名などの設定（uvが読む）
├── uv.lock               # 全員が同じバージョンで動かすための記録（コミットする）
├── .env.example          # APIキー設定のひな形（本物のキーは書かない）
├── .gitignore            # Gitに入れないファイルの指定（.env など）
├── src/ai_lie_game/
│   ├── config.py         # 設定値（テーマ、問題数、モデル名、APIキーの読み込み）
│   ├── prompts.py        # AIへの指示文
│   ├── llm.py            # OpenAI API呼び出し（再試行・JSON検査つき）
│   ├── game_a.py         # ゲームAのルールと状態管理
│   ├── game_b.py         # ゲームBのルールと状態管理
│   ├── ui.py             # Gradioの画面
│   └── main.py           # 起動の入口
├── tests/                # 自動テスト
└── docs/                 # 補足ドキュメント
```

出題の内容やAIの話し方を変えたいときは `prompts.py`、テーマや問題数は `config.py` を編集します。

## APIキーの扱い（重要）

- キーは **コードに書かず**、`.env`（または環境変数 `OPENAI_API_KEY`）から読み込みます。
- `.env` は `.gitignore` に入っているため、コミットされません。
- 万一キーをGitHubに公開してしまったら、すぐにOpenAIの管理画面でそのキーを削除（無効化）してください。

## ライセンス

MIT License
