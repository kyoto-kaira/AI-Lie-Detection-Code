# フォルダ構造の解説

| 場所 | 役割 |
|---|---|
| `README.md` | プロジェクトの説明・使い方 |
| `pyproject.toml` | 依存パッケージとプロジェクト設定（uvが読む） |
| `uv.lock` | 全員が同じバージョンを使うための固定ファイル（Git管理する） |
| `.env.example` | APIキー設定のひな形（Git管理する） |
| `.env` | 自分のAPIキー（**Git管理しない**） |
| `.gitignore` | Gitに載せないファイルの指定 |
| `src/liar_game/cases.py` | 3つの固定事件のデータと整合性チェック |
| `src/liar_game/difficulty.py` | 難易度ごとの設定（質問回数・ヒント・スコア・AIの追い詰められ方） |
| `src/liar_game/prompts.py` | 容疑者AIへのシステムプロンプトの作成 |
| `src/liar_game/interrogation.py` | 質問・証拠の開示・ヒント・推理判定（1プレイ分の状態） |
| `src/liar_game/scoring.py` | スコア計算 |
| `src/liar_game/ranking.py` | ニックネーム別の記録とランキング（JSON保存） |
| `src/liar_game/ui.py` | Gradio画面 |
| `src/liar_game/main.py` | 起動の入口 |
| `tests/` | 自動テスト（APIを呼ばずに動く） |
| `examples/demo.py` | 画面なしで、ターミナルで1問だけ試すサンプル |
| `data/ranking.json` | ランキングの記録（起動すると自動で作られる。Gitには載せない） |

## 処理の流れ
```
main.py ── ui.py ──┬── interrogation.py ──┬── cases.py       （事件データ）
                   │                      ├── difficulty.py  （難易度設定）
                   │                      ├── prompts.py     （AIへの指示）
                   │                      ├── scoring.py     （点数）
                   │                      └── OpenAI API
                   └── ranking.py ── data/ranking.json
```

## 使わなかったもの
- `setup.py`：`pyproject.toml` が代わりを担うため不要です。
