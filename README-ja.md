# Expo-Map-Generator

展示会の会場図 PDF から、検索できてオフラインでも使える会場マップ（HTML 1 ファイル）を、1 文の指示で作る Claude Code プラグイン。

## Why

展示会の会場図は PDF で配られる。検索も、ブースへの印付けも、スマホでのメモもできない。
「この会場図 PDF を見て、良い感じのマップを作って」と頼むと、`expo-map-factory` スキルが選択式の質問を最大 4 問だけしてから、自律でマップを作る。
出展者を主催者の会場図そのものの上に配置し、自動のゲートと抜き取りの目視検査で結果を確かめる。

プラグイン名は `oneshot-factory` で、次のスキルを含む。

| スキル | 役割 |
|---|---|
| `expo-map-factory` | 会場図 PDF → 会場マップ（検索、お気に入り、訪問済み、メモ、オフライン、スマホ対応） |
| `oneshot-factory` | 「1 回の入力 → 検証済みの動く成果物」を自律で作る汎用の流れ。`expo-map-factory` はこれの特化版 |
| `ddd-bdd-tdd-flow`、`external-api-tos-check`、`unresolved-questions`、`okf-open-knowledge-format`、`playwright-test`、`adr-writing-ja` | 同梱した前提スキル（それぞれ自身の LICENSE を保持） |

`adr-writing-ja` のライセンスは CC BY-NC-SA 4.0（非営利の利用に限る）。

## Install

```bash
claude plugin marketplace add krkrkrr/Expo-Map-Generator
claude plugin install oneshot-factory@expo-map-generator
```

外部ツールとして、Python 3.10 以上、`pymupdf`、`playwright` と Chromium 系ブラウザ、`tesseract`（図形で描かれたブース番号の OCR）、Node.js（初回のマップアプリのビルド）を使う。
スキルは開始前に `scripts/setup_check.py` を実行する。Python のパッケージとブラウザは自分で入れ、それ以外は OS ごとのコマンドを示す（例: Windows では `winget install --id UB-Mannheim.TesseractOCR -e`）。

## Quick Start

マップアプリを置きたいリポジトリで、Claude Code に次のように頼む。

```
https://www.inter-bee.com/assets/dl/pdf/ja/BEE26_map_web_j.pdf を見て、良い感じのマップを作って
```

成果物は `dist/<イベント>_map.html`（スマホで開く）と `dist/<イベント>_map-data.json` に出る。平易な報告は `doc/increments/<日付>-<イベント>/factory/report.md` に出る。
初回はマップアプリも `app/` に作る。2 回目以降はそれを再利用し、データだけを作り直す。
`dist/` と `work/` には主催者の著作物が入る。git に入れず、公開もしない。

## License

MIT。`skills/` に同梱した前提スキルは、それぞれ自身のライセンスに従う（各スキルのディレクトリの LICENSE を参照）。
