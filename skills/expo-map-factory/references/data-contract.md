# データとテスト用の目印の契約

生成するマップ HTML の作り（言語、構成、見た目）は自由である。ただし次の 2 つは守る。
ゲート（`check_data.py`、`smoke.py`）はこの契約だけを頼りに、中身を知らずに検査する。

1. **`map-data.json`**: HTML に埋め込むのと同じデータを、別ファイルとしても出す
2. **テスト用の目印**: HTML に `window.EXPO_MAP_DATA` と `data-testid` を付ける

---

## 1. map-data.json

```jsonc
{
  "meta": {
    "event": "展示会名 2026",
    "dates": "2026-11-18〜20",            // 任意
    "venue": "会場名",                     // 任意
    "map_pdf": "https://…/map.pdf",        // 必須: 会場図の出どころ
    "sources": ["https://…/exhibitors/"],  // 必須: 出展者情報の出どころ（複数可）
    "fetched": "2026-11-20",               // 必須: 取得日
    "notes": "推定の扱いなど"               // 任意
  },
  "pages": [                               // 必須: 会場図のページ。座標系の定義
    {"page": 1, "w": 1190.55, "h": 841.89, "label": "ホール 8・7"}
  ],
  "exhibitors": [
    {
      "id": 162,                           // 必須: 整数、一意。公式の ID があればそれ。無ければ連番
      "name": "（株）アートウィズ",          // 必須
      "booth": "2301",                     // 無ければ null
      "hall": "ホール 2",                   // 任意
      "division": "プロオーディオ部門",      // 任意: 部門、カテゴリ
      "zone": null,                        // 任意: 所属するゾーン名
      "description": "…",                  // 任意: 公式の出展説明
      "url": "https://…",                  // 任意: 公式の詳細ページ
      "logo": "https://…",                 // 任意: 外部 URL でよい（オフラインでは欠けてよい）
      "map": {                             // 位置が分からなければ null
        "page": 3, "x": 550.6, "y": 607.9, "w": 36.2, "h": 67.9,   // PDF のポイント、左上原点
        "kind": "booth",                   // booth=区画の矩形 / label=社名の文字の位置だけ
        "match": {"method": "booth-number-ocr", "score": 1.0},      // 必須: 位置の出どころ
        "inferred": false,                 // 推定で決めた位置なら true
        "extra": []                        // 同じブースの別区画（推定なら inferred: true）
      },
      "booth_note": null,                  // inferred / extra があるときは必須: 推定の理由
      "map_note": null                     // map が null のときは必須: 位置が無い理由
    }
  ],
  "zones": [                               // 任意: 出展者リスト外のまとまり
    {"name": "○○ゾーン", "page": 1, "x": 0, "y": 0, "w": 0, "h": 0, "ids": [502, 503]}
  ],
  "theme": {                               // 任意: 入口で注目ジャンルを選んだときだけ
    "genres": [{"id": "mixer", "label": "音響ミキサー", "icon": "🎚"}],
    "items": {
      "162": {
        "g": ["mixer"],                    // 当てはまるジャンル
        "p": "A",                          // 総合の優先度 S/A/B/C
        "gp": {"mixer": "A"},              // ジャンル別の優先度
        "note": "一言の理由",
        "tags": ["Dante", "AES67"],        // 任意: 対応規格など
        "evidence": "description:「…」"    // 必須: 根拠（出展説明の引用、カテゴリ登録など）
      }
    }
  },
  "geo": null                              // 任意: GPS を入れるときの対応式と出どころ
}
```

### `map.match.method` の値

| 値 | 意味 | 信頼度 |
|---|---|---|
| `override` | 人またはエージェントが画像を見て決めた。`note` に理由 | 理由しだい |
| `booth-number` | PDF の文字のブース番号と一致 | 高 |
| `booth-number-ocr` | 図形で描かれた番号を OCR で読み、一致 | 高（誤読は名前照合と食い違うことで見つかる） |
| `name` | 社名の照合。`score` と `label`（PDF 上の表記）を持つ | score しだい |

`match_booths.py` の出力はそのまま、この `map` の形になっている。

---

## 2. テスト用の目印

| 目印 | 付ける場所 | 条件 |
|---|---|---|
| `window.EXPO_MAP_DATA` | グローバル変数 | `map-data.json` と同じ内容のオブジェクト |
| `data-testid="search"` | 検索の入力欄 | 入力すると即座に一覧が絞られる |
| `data-testid="exhibitor-item"` + `data-id="<id>"` | 一覧の各行 | 絞り込みなしで全件が DOM にある（仮想スクロールにしない） |
| `data-testid="sheet-tab"` | ページ切り替えのタブ | 会場図のページ数と同じかそれ以上 |
| `data-testid="map-image"` | 背景の会場図の `<img>` | 表示中のものは読み込み済み |
| `data-testid="booth"` + `data-ids="<id>,<id>"` | 地図上の区画 | 表示中のページの区画だけが DOM にある |
| `data-testid="detail"` | 詳細の表示領域 | 開いているときだけ見える。社名を含む |
| `data-testid="fav"` + `aria-pressed` | 詳細の中のお気に入りボタン | `"true"` / `"false"` |
| `data-testid="visited"` + `aria-pressed` | 詳細の中の訪問済みボタン | 同上 |

目印はテストのためだけのものではない。`aria-pressed` は支援技術にも状態を伝える（IR-11）。
