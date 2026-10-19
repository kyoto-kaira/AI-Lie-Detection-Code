# フォルダ構造の解説（初心者向け）

## なぜ分けるのか

Colabでは1つのノートブックにセルを順番に並べますが、チームで開発するときは
**役割ごとにファイルを分ける**と、どこを直せばよいか分かりやすく、同時に作業しても衝突しにくくなります。

## Colabのセルとの対応

| Colabのセル | このプロジェクトのファイル |
|---|---|
| 1. 設定 | `src/ai_lie_game/config.py` |
| 2. プロンプト | `src/ai_lie_game/prompts.py` |
| 3. API呼び出し | `src/ai_lie_game/llm.py` |
| 4. ゲームA、6. 状態管理（A） | `src/ai_lie_game/game_a.py` |
| 5. ゲームB、6. 状態管理（B） | `src/ai_lie_game/game_b.py` |
| 7. 画面 | `src/ai_lie_game/ui.py` と `main.py` |
| 動作確認（RUN_SELF_TEST） | `tests/` |

## 各ファイル・フォルダの役割

- **`pyproject.toml`**：プロジェクトの設計図。名前、必要なパッケージ、起動コマンド（`ai-lie-game`）を書く。
  昔は `requirements.txt` や `setup.py` に分かれていたものを、今はこの1ファイルにまとめるのが主流。
  uv を使う場合、`requirements.txt` と `setup.py` は不要。
- **`uv.lock`**：`uv sync` / `uv run` で自動生成される「実際に入れたバージョンの記録」。
  コミットしておくと、全員が同じ環境になる。
- **`.env` / `.env.example`**：秘密の設定置き場。`.env` は各自が作り、Gitに入れない。`.env.example` はひな形でGitに入れる。
- **`.gitignore`**：Gitが無視するファイルの一覧。`.env` と `.venv/` が特に大事。
- **`src/`**：プログラム本体。`src/ai_lie_game/` が「パッケージ」で、`__init__.py` があるフォルダがパッケージになる。
- **`tests/`**：自動テスト。`uv run pytest` で一括実行できる。
- **`docs/`**：説明資料。

## 標準構成から省いたもの

- `setup.py`：`pyproject.toml` で代替できるため不要。
- `examples/`、`data/`：このアプリでは使わないため省略。必要になったら足せばよい。
