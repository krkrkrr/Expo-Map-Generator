# マップアプリの作り方（初回だけ）

`app/` が無いときに、マップアプリを作る手順である。
流れはシナリオ → プロパティテスト → TDD で、仕様は合議で決め、網羅はゲートで示す。**他のスキルを読まなくても、ここだけで足りる。** 規則、推測合議、verifier、停止条件は `factory-rules.md` に従う。

一般的な DDD → BDD → TDD の流れから、意図して落としたもの: どのコンテキストに属するかの判定（「会場マップ」の 1 つに固定）、要件ヒアリング（入力は下の材料で足りる）、利用者の承認ゲート、コンテキストマップと S/U 図、文書の食い違いの整理、ADR を `Accepted` にする流れ、OKF の検査。

---

## 1. 前提

- **境界づけられたコンテキストは「会場マップ」の 1 つだけ。** 新しく立てない。データの取り込み（SKILL.md のステージ 2〜4）はアプリの外の作業で、アプリは `map-data.json` とページ画像を読むだけ
- **仕様の材料は次の 5 つに限る:** SKILL.md の「固定の前提」、`intake.md`、`good-map.md`（GM）、`factory-rules.md` の IR、`data-contract.md`。それ以外の判断は推測合議（`factory-rules.md` 3 章）で決める
- **利用者に見せて承認を求めない。** 承認の代わりは、各手順の「通過条件」である
- 技術の既定値は憲章の `DEFAULTS`（TypeScript + Vite + vite-plugin-singlefile、Vitest + fast-check、Playwright、localStorage のみ）

## 2. 置き場所

| 物 | 場所 |
|---|---|
| ユースケース | `doc/map-app/use-cases.md`（`UC-xx`） |
| 規則、不変条件、状態遷移表 | `doc/map-app/rules.md`（`R-xx`、`INV-xx`） |
| 用語、単位、境界値の番兵 | `doc/map-app/glossary.md` |
| シナリオ | `doc/map-app/features/<ユースケース名>.feature` |
| 合議の記録 | `doc/increments/<日付>-<slug>/factory/council/` |
| テストリスト | `doc/increments/<日付>-<slug>/test-list.md` |
| ソース、テスト | `app/src/`、`app/test/unit/`、`app/test/integration/`（PBT）、`app/test/e2e/` |

ID は文書をまたいで一意にし、接頭辞（`UC-`、`R-`、`INV-`）を必ず付ける。図を描くなら Mermaid で、1 枚 40 行以内。

## 3. 手順

### 手順 1. 仕様の下書き

1. GM と IR の各項目を読み、当てはまるものから `use-cases.md` を作る。ユースケースは利用者の目的の単位にする（例: 「行きたいブースに印を付ける」「メモを持ち帰る」）。各行に `source`
2. `rules.md` に規則と不変条件を書く。**状態を持つもの**（お気に入り、訪問済み、メモ、絞り込みの設定、読み込み時の統合）は、状態 × 操作の **状態遷移表** にする。不正な遷移の欄も埋める
3. `glossary.md` に用語と、境界値の番兵を書く（例: 検索語 0 文字、メモ 0 文字と上限、出展者 0 社と 2,000 社、ブース番号の全角と半角）。上限などの数値が材料に無ければ推測合議で決める

### 手順 2. 仕様合議

人数は 2 役（`personal`）。

| 役 | 見ること |
|---|---|
| 利用者の代弁 | 固定の前提と GM から外れていないか。膨らみすぎていないか。非エンジニアが迷う所は無いか |
| テスト設計者 | 検証できない記述、網羅の穴、期待値が無い振る舞い、状態遷移表の空欄 |

1. **最初は互いに見せない。** 各役を別のサブエージェントで動かし、次の形で指摘を出させる

   ```yaml
   - id: R-<役>-<連番>
     target: <use-cases|rules|glossary|feature>:<ファイル>#<見出し>
     finding: <何が問題か、1 文>
     severity: blocker | major | minor
     proposal: <どう直すか、1 文>
     source: skill-fixed | catalog:GM-xx | catalog:IR-xx | contract | inference
   ```

   保存先は `factory/council/round-<n>-<役>.md`
2. **裁定役（別のサブエージェント）が集約する。** 重複をまとめる。機械で判定できるもの（ID、リンク、Gherkin が実行できるか）は投票せずゲートに任せる。一致した指摘は反映する。割れた指摘は根拠を示させて 1 巡だけ議論させ、それでも割れたら `factory-rules.md` 3 章の裁定順で決める。往復は `max_council_rounds`（2）まで
3. **出どころで削る。** `source` の無い行を削る

**通過条件**: 合議が終わり、文書の検査（6 章の C1 と ID・リンクの検査）が GREEN。`factory/council/verdict.md` に `approved-by-council` と書き、コミットする（`docs(map-app): add use cases and rules`）。

### 手順 3. シナリオ（Gherkin）

ユースケースごとに 1 ファイル。各シナリオにタグを付ける。

- 種類: `@happy @boundary @error @rule @concurrency`（各ユースケースに 5 種類すべて）
- 出どころ: `@GM-xx`、`@IR-xx`、`@R-xx`、`@INV-xx`

```gherkin
@UC-03
Feature: 行きたいブースに印を付ける
  非エンジニアの来場者として
  回りたい会社にお気に入りを付けたい
  当日スマホで迷わず回るために

  @happy @GM-10
  Scenario: 一覧からお気に入りを付ける
    Given 出展者「アシダ音響」が一覧にある
    When 一覧の「アシダ音響」の ★ を押す
    Then 「アシダ音響」がお気に入りになる
    And 地図の区画がお気に入りの色になる

  @concurrency @IR-03
  Scenario: ★ を素早く 2 回押す
    When 一覧の「アシダ音響」の ★ を 2 回続けて押す
    Then 「アシダ音響」はお気に入りではない
```

シナリオは思いつきで書かず、**手順 1 の文書から導く**: 状態遷移表の各欄 → シナリオ、glossary の番兵 → 境界値、設定の組み合わせが 4 つ以上 → ペアワイズ法。

**反論役にシナリオを足させる。** 書いた作業役とは別のサブエージェントに、「このモデルが壊れる操作の列」を出させる。

**通過条件**: 6 章の C1〜C3 が GREEN。コミットした時点で `.feature` は **固定**（以降は追加だけ）。`docs(map-app): add feature files`

### 手順 4. プロパティテスト

1. 各シナリオから不変条件を取り出し、`rules.md` の `INV-xx` に追記する。問う観点:
   - 事後条件（この操作の後、X が常に成り立つ）
   - 否定（この操作は Y を決して生まない）
   - 往復（書き出し → 読み込みで元に戻る）
   - 冪等（2 回適用しても 1 回と同じ。読み込みの統合など）
   - 等価（検索語の全角と半角、大文字と小文字で同じ結果）
2. `app/test/integration/` に fast-check で書く。シュリンクを有効にする。**状態を持つ機能には、モデルに対するステートフル PBT を 1 つ以上**（印とメモの保存、読み込みの統合）
3. `app/test/e2e/` に Playwright で、**ビルドした HTML を `file://` で開いて** 主要な流れを確かめる。テスト用の目印は `data-contract.md` の 2 章に従う

**通過条件**: テストが **正しい理由で落ちる**（実装が無いので落ちる。構文エラーで落ちるのではない）ことを確かめてコミットする。この時点で **固定**。`test(map-app): add property-based and e2e tests`

### 手順 5. TDD で実装する

1. **テストリストを先に全部書く**（`test-list.md`、チェックボックスの一覧）。まだコードを書かない
2. **縦のスライスに割る。** スライス 0 は曳光弾: データを埋め込んだ HTML 1 ファイルがビルドでき、会場図が出て、テスト用の目印があり、`smoke.py` が通る。中身はほぼフェイクでよい。以降のスライスで、フェイクを 1 つずつ本物にする。1 スライスの差分は 400 行以下
3. **1 項目ずつ Red → Green → Refactor。**
   - Red: `app/test/unit/` に失敗するテストを 1 つ書く。落ちる理由がアサーションであることを確かめる。テスト名は文として読める形（「検索: 全角の社名でも半角の入力で見つかる」）
   - Green: 通る最も単純なコードを書く。全テストを回し、退行が無いこと
   - Refactor: 重複を除き、名前を直す。全テストを回す。リストに `[x]`
   - 実装がフェイク（決め打ち）のままなら、別の具体例で 2 つ目のテストを足して一般化を強制する（三角測量）
4. **prove-test**: スライスの終わりに、`app/src/` の差分だけを戻して（`git stash push -- app/src`）、そのスライスで足したテストが落ちることを確かめ、戻す（`git stash pop`）。落ちないテストは書き直す（固定済みのテストではなく、そのスライスで足した単体テストに限る）
5. スライスごとに 6 章のゲートを回し、verifier（`factory-rules.md` 5 章）に `accepted` をもらってからコミットする（`feat(map-app): <スライス名>`）。Red-Green-Refactor の途中ではコミットしない

### 手順 6. ビルドの形

アプリは次の形のビルドを持つ。2 回目以降のイベントでは、これだけを使う。

```
npm --prefix app run build -- --data dist/<slug>_map-data.json --images work/<slug>/pages --out dist/<slug>_map.html
npm --prefix app run gates        # 最後の行に FACTORY_GATES: level=app ...
```

## 4. 網羅ゲート（`npm run gates` が検査する）

「全部試す」は不可能である。代わりに網羅の基準を定め、満たしたことを機械で示す。1 つでも欠けたら RED。

| ID | 基準 | 確かめ方 |
|---|---|---|
| C1 | `use-cases.md` の全ユースケースに `.feature` がある | 文書の検査 |
| C2 | 各ユースケースに `@happy @boundary @error @rule @concurrency` が揃う | タグを数える |
| C3 | `rules.md` の全 `R-xx` と `INV-xx` に、シナリオとテストが 1 つ以上ある | ID ↔ タグ ↔ テスト名の対応表 |
| C4 | 状態遷移表の全欄（不正な遷移を含む）にテストがある | 表から期待集合を作り、テスト名と突き合わせる |
| C5 | 状態を持つ機能にステートフル PBT が 1 つ以上ある | テストファイルを検査 |
| C6 | `.feature` の全ステップが実際に実行される。未定義と保留が 0 | 実行結果 |
| C7 | 当てはまる IR-xx と GM-xx のすべてにテストがある | `@IR-xx`、`@GM-xx` タグを数える |
| C8 | 境界値のシナリオが `glossary.md` の番兵から導かれている | glossary と `@boundary` を突き合わせる |

加えて、types、lint、unit、integration（PBT）、e2e、文書の検査（ID の重複と接頭辞、リンク切れ、図の行数）を回す。どれかが実行できなければ `MISCONFIGURED`。
