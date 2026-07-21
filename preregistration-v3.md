# perceptive-world-demo
# Tier A / Tier B LOD Test Preregistration v3

## 0. 文書メタデータ

```yaml
document: preregistration-v3.md
project: perceptive-world-demo
scope: LOD regression testing
version: 3.0-rc2
status: approval-pending

design_reference:
  branch: master
  head_short_sha: 5d770c3
  acceptance_checkpoint: false

checkpoint:
  tag: tierA-lod-v3
  commit: "5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f"
  type: annotated-tag

baseline:
  tag: tierA-hero-fix-v2
  commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
  test_branch: test/tier-a-v2
  known_result:
    selftest_passed: 37
    verification_passed: 171

test_harness:
  branch: test/tier-a-v3
  included_in_target_tag: false

roles:
  implementation: Claude Code
  execution: Codex
  test_design: ChatGPT
```

本書は、単一の `index.html` で構成される2D JRPG見た目デモ `perceptive-world-demo` の詳細度、LODシステムに対する、v3受け入れテストの事前登録である。

v3の正式な対象コミットは、Claude Codeが実装完了後にannotated tagを作成した時点で確定する。

```text
tag:    tierA-lod-v3
commit: 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f
```

正式SHA通知後、本文中の `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f` をそのSHAへ置換する。

SHA置換時に変更してよいのは、次だけである。

- `checkpoint.commit`
- 本文中の `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f`
- 対象タグの確認情報
- Gitコマンド例に含まれる対象SHA

テスト条件、キー集合、閾値、例外、シナリオ、合否境界を対象結果に合わせて変更してはならない。

---

# 1. 目的

v3は二層構成とする。

## 1.1 Tier A v3

ブラウザを使用しない静的検査である。

次を検証する。

1. Tier A v2のアトラス整合検査を継承する。
2. Tier A v2のhero方向検査を継承する。
3. LODテーブル間のキー、参照、値の整合を検査する。
4. LOD用の独立インライン画像をPNGとして検証する。
5. LOD画像がbase／HIアトラスから独立していることを検査する。
6. v2で凍結したアトラスおよび描画補助コードが変更されていないことを検査する。
7. 各checkerについてnegative self-testを実行する。
8. JSONレポートとexit codeで機械的に合否を決定する。

Tier A v3はv3受け入れにおける必須ゲートである。

## 1.2 Tier B v3

ヘッドレスChromiumを使用する実挙動検査である。

次を検証する。

- ランドマークLOD遷移
- LOD画像のDOM表示
- LODイベント効果
- 取得済み処理
- LOD間メッセージ消去
- 敵LOD遷移
- 単体／複数戦の対象選択
- 敵HP、HPバー、弱点表示
- 詳細表示中のターン凍結
- 弱点表示が戦闘計算へ影響しないこと
- 勝利、全滅、逃走時のオーバーレイクリーンアップ

Tier BはCodex環境でChromiumと必要テストフックを使用できる場合に実行する。

Codex環境でブラウザを起動できない場合、または対象タグに必要フックが存在しない場合は、Tier Bを `blocked` として記録する。

その場合の判定は次とする。

```text
Tier A pass:
  static gate = pass

Tier B blocked:
  behavior gate = blocked

overall certification:
  partial-static-pass
```

Tier Bを実行でき、behavior invariantがfailした場合は、Tier Aがpassでも完全受け入れ不可とする。

---

# 2. チェックポイントとテスト分離

## 2.1 v3対象タグ

予定タグ:

```text
tierA-lod-v3
```

予定コミット:

```text
5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f
```

通常実行では、次を確認する。

- 対象がGitリポジトリである
- `HEAD == 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f`
- `tierA-lod-v3^{commit} == 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f`
- `tierA-lod-v3` がannotated tagである
- 実行前の対象worktreeがcleanである
- 実行後の対象worktreeがcleanである
- 実行前後でHEADが変化していない

不一致はsetup failureとする。

## 2.2 v2基準点

Tier A v2の基準点は次である。

```text
tag:    tierA-hero-fix-v2
commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
```

v2のタグ、テストブランチ、preregistration、閾値、既存レポートを変更してはならない。

v3 checkerは `test/tier-a-v3` でv2 checkerを継承する。

## 2.3 テストファイルの隔離

次のファイルはv3対象タグに含めない。

```text
preregistration-v3.md
TIER_A_RUNBOOK_V3.md
tests/tier_a.py
tests/tier_b/
playwright.config.mjs
package.json
package-lock.json
tier_a_v3_report.json
tier_a_v3_selftest_report.json
tier_b_v3_report.json
```

テスト一式は次のブランチに置く。

```text
test/tier-a-v3
```

対象タグには、実装、画像、アセット、およびTier Bに必要な製品側テストフックだけを含める。

---

# 3. 推奨worktree構成

```text
C:\Users\pipe_render\
├─ perceptive-world-demo-v2-baseline\
│  └─ detached checkout: tierA-hero-fix-v2
│
├─ perceptive-world-demo-v3-target\
│  └─ detached checkout: tierA-lod-v3
│
└─ perceptive-world-demo-v3-tests\
   ├─ preregistration-v3.md
   ├─ TIER_A_RUNBOOK_V3.md
   ├─ tests\
   │  ├─ tier_a.py
   │  └─ tier_b\
   ├─ playwright.config.mjs
   ├─ package.json
   └─ package-lock.json
```

Tier A通常実行:

```powershell
python tests\tier_a.py `
  --baseline-root C:\Users\pipe_render\perceptive-world-demo-v2-baseline `
  C:\Users\pipe_render\perceptive-world-demo-v3-target
```

Tier A self-test:

```powershell
python tests\tier_a.py --selftest
```

Tier B:

```powershell
npx playwright test --config=playwright.config.mjs
```

---

# 4. コミット済みファイル限定ポリシー

Tier Aは、v2とv3双方についてコミット済みblobだけを検査対象とする。

概念上、次と同等の方法で取得する。

```powershell
git -C <repo> show HEAD:index.html
git -C <repo> show HEAD:assets/hi/atlas_hi.png
git -C <repo> show HEAD:assets/hi/manifest_hi.json
```

未追跡ファイル、未コミット変更、生成途中ファイル、ブラウザキャッシュ、過去レポートは入力に使用しない。

対象worktreeがdirtyである場合、コミットblobの内容が正常でもcheckpoint integrity failureとする。

---

# 5. Tier A実行制約

Tier Aで使用できるもの:

```text
Python 3
Python標準ライブラリ
Pillow
numpy
Gitの読み取りコマンド
```

禁止するもの:

```text
ブラウザ
ヘッドレスブラウザ
JavaScript実行
Node.js
Playwright
Puppeteer
SciPy
OpenCV
ImageMagick
ネットワークアクセス
外部ダウンロード
実行時画像生成
tools/conform.pyの実行
tools/conform_hi.pyの実行
```

Tier Aはオフライン、決定論的、ブラウザ非依存でなければならない。

---

# 6. Tier A v2検査の継承

v3の `tests/tier_a.py` は、v2のA／B checkerを変更せず継承する。

## 6.1 A: アトラス整合

継承する検査:

```text
A1  矩形値の妥当性
A2  atlas範囲内
A3  インラインbase64 PNG妥当性
A4  矩形非重複
A5  base必須34名
A6  SPR_HIがSPRの部分集合
A7  inline SPR_HIとdisk manifest_hi.jsonの一致
A8  inline ATLAS_HIとdisk atlas_hi.pngのRGBA一致
A9  hero 9フレームがbase／HI双方に存在
```

必須34名:

```text
grass
dirt
water
flower

hero_down_0
hero_down_1
hero_down_2
hero_up_0
hero_up_1
hero_up_2
hero_side_0
hero_side_1
hero_side_2

tree
well
shrine
torch
house
goblin
sentry
chief

ifloor
iwall
idoor

npc_elder
npc_herb

table
chair
shelf
bed
plant
barrel
cauldron
rug
```

## 6.2 B: hero方向

固定値:

```text
HEAD_REGION_FRACTION = 0.50
T_FACE               = 0.08
T_NOFACE             = 0.01
T_CENTER             = 0.05
T_SIDE_RIGHT         = 0.57
T_DOWN_UP_RATIO      = 5.0
```

肌マスク:

```text
alpha > 0
R > 185
140 < G < 205
110 < B < 180
R > G > B
```

頭部領域:

```text
不透明bbox上端から高さ50%
y < top + ceil(0.50 × bbox_height)
```

方向条件:

```text
up:
  face_ratio <= 0.01

down:
  DOWN_FACE:
    face_ratio >= 0.08

  DOWN_CENTER:
    abs(ncx - 0.50) <= 0.05

side:
  SIDE_FACE:
    face_ratio >= 0.08

  SIDE_RIGHT:
    ncx > 0.57

relative:
  down_face_ratio >= 5.0 × up_face_ratio
```

`DOWN_FACE` と `DOWN_CENTER` は別check IDとして出力する。

v3のLOD追加を理由に、A／Bの閾値、肌マスク、頭部定義、境界演算子を変更してはならない。

---

# 7. Tier A静的抽出方式

## 7.1 既存A／B抽出

`SPR`、`SPR_HI`、`ATLAS.src`、`ATLAS_HI.src` の抽出は、承認済みv2 checkerの実装を継承する。

JavaScriptは実行しない。

## 7.2 LODテーブル抽出

次の宣言を静的に取得する。

```text
FOCUS_CAP
FOCUS_TXT
FOCUS_EVENT
FOCUS_IMG
TAKEN_MSG
ENEMY_KINDS
ENEMY_IMG
ENEMY_WEAK
ROOM_SUBJ
```

LODテーブルはJSONに限定されないため、次を理解する決定論的な軽量スキャナを使用する。

- 文字列
- エスケープ
- 配列
- object literal
- identifier
- 数値
- boolean
- null
- arrow function
- function expression
- function reference
- コメント
- 括弧深度

関数本体は実行せず、生ソースが空でないことだけを確認する。

同名宣言が複数存在し一意に解決できない場合はfailとする。

## 7.3 独立画像src抽出

独立画像のdata URLは、次に相当する一意な代入を正規表現で抽出する。

```javascript
IMAGE_IDENTIFIER.src = "data:image/png;base64,...";
```

許容する差:

- 空白
- 改行
- single quote／double quote
- `const`／`let`
- セミコロンの前後空白

base64 payload自体は次の文字集合に限定する。

```text
A-Z
a-z
0-9
+
/
=
```

payload内の改行、空白、無効文字を暗黙除去してはならない。

同じidentifierに複数の異なるsrc代入がある場合はfailとする。

---

# 8. C: ランドマークLODテーブル整合

ランドマークの正規集合:

```text
LANDMARK_KEYS = {
  well,
  shrine,
  lookout,
  elder,
  herb
}
```

レポート上の固定順序:

```text
well
shrine
lookout
elder
herb
```

## C1. FOCUS_CAPキー

`FOCUS_CAP` のキー集合は次と完全一致する。

```text
{well, shrine, lookout, elder, herb}
```

各値は空でない文字列でなければならない。

## C2. FOCUS_TXTキー

`FOCUS_TXT` のキー集合は次と完全一致する。

```text
{well, shrine, lookout, elder, herb}
```

各値は空でない文字列でなければならない。

## C3. FOCUS_EVENTキー

`FOCUS_EVENT` のキー集合は次と完全一致する。

```text
{well, shrine, lookout, elder, herb}
```

各値は、空でないfunction reference、function expression、arrow function、または一意なイベントidentifierでなければならない。

Tier Aはイベントを実行しない。

## C4. FOCUS主要テーブル一致

次を必須とする。

```text
keys(FOCUS_CAP)
  == keys(FOCUS_TXT)
  == keys(FOCUS_EVENT)
  == LANDMARK_KEYS
```

欠落、余分なキー、重複キーはfailとする。

## C5. FOCUS_IMGの既知非対称

`FOCUS_IMG` の正規キー集合は次である。

```text
{well, shrine, elder, herb}
```

`lookout` は含めない。

```text
keys(FOCUS_IMG)
  == LANDMARK_KEYS - {lookout}
```

これは意図的な非対称である。

物見櫓は村マップの通常ズーム画像経路を使用せず、`drawTower`／`towerKey` による独立登攀シーケンスを使用する。

`FOCUS_IMG.lookout` が存在した場合も、事前登録構造からの逸脱としてfailとする。

## C6. FOCUS_IMG参照

各キーは、独立Image identifierへ一意に解決されなければならない。

現行設計の意味対応:

```yaml
well: WELL_FOCUS
shrine: SHRINE_FOCUS
elder: ELDER_FOCUS
herb: HERB_FOCUS
```

identifier名を変更する場合でも、各意味スロットが一意の独立Imageへ解決される必要がある。

## C7. lookout専用画像

物見櫓は次の3画像を独立して持たなければならない。

```text
TOWER_FULL
TOWER_TOP
TOWER_VIEW
```

意味:

```yaml
TOWER_FULL: 櫓全景
TOWER_TOP: 登攀／上部詳細
TOWER_VIEW: +3遠望
```

`TOWER_VIEW` は+3でfull-bleed表示される画像である。

`FOCUS_IMG.lookout` による代替は認めない。

## C8. TAKEN_MSG

`TAKEN_MSG` は次の5キーを持たなければならない。

```text
{well, shrine, lookout, elder, herb}
```

各値は空でない文字列でなければならない。

Tier Bは再度Zを押した時の表示文言を、この静的値と比較する。

---

# 9. C: 敵LODテーブル整合

## C9. ENEMY_KINDS

`ENEMY_KINDS` は順序を含め、次と完全一致する。

```javascript
["goblin", "sentry", "chief"]
```

次はfail:

- 欠落
- 追加
- 重複
- 順序変更
- 非文字列値

## C10. ENEMY_IMG kind

`ENEMY_IMG` のtop-levelキー集合は次と完全一致する。

```text
{goblin, sentry, chief}
```

## C11. ENEMY_IMG LODレベル

各kindはLOD 1、2、3をすべて持たなければならない。

正規化後:

```text
keys(ENEMY_IMG[kind]) == {1, 2, 3}
```

数値キーと文字列キーは同じものとして正規化してよい。

```text
1
"1"
```

ただし欠落、余分なLOD、重複した等価キーはfailとする。

合計9意味スロットを必須とする。

```text
goblin[1]
goblin[2]
goblin[3]

sentry[1]
sentry[2]
sentry[3]

chief[1]
chief[2]
chief[3]
```

各値は独立Image identifierへ一意に解決されなければならない。

## C12. ENEMY_WEAKキー

`ENEMY_WEAK` のキー集合は次と完全一致する。

```text
{goblin, sentry, chief}
```

## C13. ENEMY_WEAK値

固定値:

```yaml
goblin: まほう
sentry: たたかう(物理)
chief: まほう
```

前後空白だけを除去して比較する。

同義語変換、翻訳、括弧除去は行わない。

## C14. 敵テーブル集合一致

次を必須とする。

```text
set(ENEMY_KINDS)
  == keys(ENEMY_IMG)
  == keys(ENEMY_WEAK)
```

## C15. 敵基礎値の静的記録

Tier B fixture検証用として、現行敵基礎値をレポートへ抽出する。

```yaml
goblin:
  hp: 5
  atk: 0
  dmg: [1, 2]
  target: 6

sentry:
  hp: 5
  atk: 0
  dmg: [1, 2]
  target: 6

chief:
  hp: 18
  atk: 2
  dmg: [2, 5]
  target: 8
```

これらの定義元が静的に一意に解決できない場合はfailとする。

Tier Bは開始直後のsnapshotがこの値と整合することを確認する。

---

# 10. C: ROOM_SUBJ整合

## C16. ROOM_SUBJキー

`ROOM_SUBJ` のキー集合は次と完全一致する。

```text
{elder, herb}
```

## C17. ROOM_SUBJ必須フィールド

各subjectは少なくとも次を持つ。

```text
room
npcImg
tile
```

追加フィールドは許容する。

## C18. room画像参照

次の意味スロットは独立Image identifierへ一意に解決されなければならない。

```text
ROOM_SUBJ.elder.room
ROOM_SUBJ.herb.room
```

現行設計の対応:

```yaml
elder.room: ELDER_ROOM
herb.room: HERB_ROOM
```

## C19. npcImg画像参照

次の意味スロットも独立Image identifierへ一意に解決されなければならない。

```text
ROOM_SUBJ.elder.npcImg
ROOM_SUBJ.herb.npcImg
```

現行設計の対応:

```yaml
elder.npcImg: ELDER_NPC
herb.npcImg: HERB_NPC
```

## C20. tile

`tile` は次のいずれかへ静的に解決できなければならない。

```javascript
[x, y]
```

または:

```javascript
{x: x, y: y}
```

条件:

```text
xとyはbooleanでない整数
x >= 0
y >= 0
```

配列の場合は要素数が正確に2でなければならない。

---

# 11. D: 独立インライン画像の健全性

## D1. 対象意味スロット

検査対象は合計20意味スロットである。

### FOCUS_IMG: 4

```text
well
shrine
elder
herb
```

### 物見櫓: 3

```text
TOWER_FULL
TOWER_TOP
TOWER_VIEW
```

### ROOM_SUBJ: 4

```text
elder.room
elder.npcImg
herb.room
herb.npcImg
```

### ENEMY_IMG: 9

```text
goblin[1..3]
sentry[1..3]
chief[1..3]
```

同じidentifierを複数意味スロットで使用している場合、その事実をレポートする。

画像再利用自体は、本v3ではそれだけを理由にfailとしない。

## D2. 独立Image構造

各意味スロットは、最終的に次に相当する構造へ一意に解決されなければならない。

```javascript
const IMAGE_ID = new Image();
IMAGE_ID.src = "data:image/png;base64,...";
```

次はfail:

- identifierが解決できない
- `new Image()` がない
- `.src` がない
- `.src` が複数あり一意でない
- `ATLAS` を参照する
- `ATLAS_HI` を参照する
- atlas矩形情報を画像値として参照する
- 外部URLを使用する

## D3. data URL

各画像srcは次で始まらなければならない。

```text
data:image/png;base64,
```

strict base64 decodeを使用する。

無効文字、余分な空白、改行、不正paddingはfailとする。

## D4. PNG妥当性

各画像について次を必須とする。

- PillowがPNGと認識する
- `verify()` が成功する
- 再openできる
- RGBA変換できる
- `width > 0`
- `height > 0`
- 全pixelをdecodeできる

レポート項目:

```text
semantic slot
image identifier
PNG byte length
width
height
PNG SHA-256
RGBA SHA-256
src assignment count
Image construction count
```

## D5. アトラスからの独立性

各LOD画像は次をすべて満たす。

1. identifierが `ATLAS` ではない
2. identifierが `ATLAS_HI` ではない
3. 専用の `new Image()` 宣言を持つ
4. 専用のインラインPNG srcを持つ
5. src payloadが `ATLAS.src` と同一ではない
6. src payloadが `ATLAS_HI.src` と同一ではない
7. `SPR`／`SPR_HI` の矩形を画像値として参照しない
8. LODテーブルからImage identifierとして参照される

この検査は「画像がアトラス内の矩形として追加された」のではなく、「アトラス外の独立Imageとして実装された」ことを確認する。

---

# 12. D: v2凍結領域との完全一致

v3はLODコンテンツを追加しても、hero/base/HIアトラス経路を変更しない。

比較基準:

```text
tierA-hero-fix-v2
13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
```

## D6. 凍結対象一覧

`index.html` 内で次を比較する。

```text
SPR宣言
SPR_HI宣言
ATLAS.src代入
ATLAS_HI.src代入
sprAt関数
drawHeroImg関数
blit系関数
```

コミット済みファイルとして次を比較する。

```text
assets/hi/atlas_hi.png
assets/hi/manifest_hi.json
```

## D7. SPRソース一致

v2とv3の `SPR` 宣言について、宣言開始から終端セミコロンまでのUTF-8 bytesが完全一致しなければならない。

空白、改行、キー順序も含め、正規化しない。

追加検証として、JSON parse後の構造一致も確認する。

## D8. SPR_HIソース一致

`SPR_HI` も同じ条件で比較する。

```text
raw source bytes equal
parsed structure equal
```

## D9. ATLAS.src一致

`ATLAS.src` の代入文全体を、v2とv3でbyte比較する。

base64 payloadだけでなく、対象代入文のUTF-8 bytesが一致しなければならない。

追加検証:

```text
decoded PNG bytes equal
dimensions equal
RGBA pixel array equal
```

## D10. ATLAS_HI.src一致

`ATLAS_HI.src` についても同じ条件を適用する。

## D11. sprAt一致

v2とv3の `sprAt` 関数を、関数宣言開始から対応する閉じ括弧まで抽出し、UTF-8 byte単位で比較する。

複数宣言、抽出不能、差異はfailとする。

## D12. drawHeroImg一致

`drawHeroImg` についても、完全な関数ソースをbyte比較する。

## D13. blit系一致

v2 baselineから、top-level function declarationのうち関数名が次に一致するものを列挙する。

```text
^blit
```

v3では:

- 同じ関数名集合が存在する
- 各関数ソースがbyte一致する
- 関数の追加、削除、改名がない

ことを必須とする。

実際の関数名集合はv2 baselineから機械的に確定し、レポートに記録する。

## D14. disk HI atlas一致

次のGit blob bytesがv2とv3で完全一致しなければならない。

```text
assets/hi/atlas_hi.png
```

追加検証:

```text
PNG dimensions equal
RGBA equal
```

## D15. disk HI manifest一致

次のGit blob bytesがv2とv3で完全一致しなければならない。

```text
assets/hi/manifest_hi.json
```

parse後のJSON構造一致も追加確認する。

## D16. 凍結比較の優先度

v2のA／Bテストがpassしても、D7〜D15の完全一致を代替しない。

たとえば、同じhero方向条件を満たす別画像へ置き換えられていた場合、A／Bはpassし得るが、Dはfailする。

---

# 13. Tier A negative self-test

実行:

```powershell
python tests\tier_a.py --selftest
```

self-testはv2／v3実リポジトリを使用せず、すべて決定論的なin-memory fixtureで行う。

v2で承認済みの37 self-testをすべて継承する。

さらにC／D用negative testを追加する。

## 13.1 FOCUS系

```text
SELF.C1.FOCUS_CAP_MISSING_KEY
SELF.C2.FOCUS_CAP_EXTRA_KEY
SELF.C3.FOCUS_TXT_MISSING_KEY
SELF.C4.FOCUS_EVENT_MISSING_KEY
SELF.C5.FOCUS_EVENT_EMPTY_VALUE
SELF.C6.FOCUS_MAIN_KEYSET_MISMATCH
SELF.C7.FOCUS_IMG_LOOKOUT_PRESENT
SELF.C8.FOCUS_IMG_REQUIRED_KEY_MISSING
SELF.C9.FOCUS_IMG_UNRESOLVED_IMAGE
SELF.C10.TOWER_IMAGE_MISSING
SELF.C11.TAKEN_MSG_MISSING_KEY
SELF.C12.TAKEN_MSG_EMPTY
```

## 13.2 敵テーブル

```text
SELF.C13.ENEMY_KINDS_MISSING
SELF.C14.ENEMY_KINDS_EXTRA
SELF.C15.ENEMY_KINDS_DUPLICATE
SELF.C16.ENEMY_KINDS_ORDER_CHANGED
SELF.C17.ENEMY_IMG_KIND_MISSING
SELF.C18.ENEMY_IMG_LEVEL_MISSING
SELF.C19.ENEMY_IMG_LEVEL_EXTRA
SELF.C20.ENEMY_IMG_UNRESOLVED
SELF.C21.ENEMY_WEAK_KEY_MISMATCH
SELF.C22.ENEMY_WEAK_VALUE_WRONG
SELF.C23.ENEMY_BASE_STAT_MISMATCH
```

## 13.3 ROOM_SUBJ

```text
SELF.C24.ROOM_SUBJ_KEY_MISSING
SELF.C25.ROOM_SUBJ_EXTRA_KEY
SELF.C26.ROOM_FIELD_MISSING
SELF.C27.ROOM_IMAGE_UNRESOLVED
SELF.C28.NPC_IMAGE_UNRESOLVED
SELF.C29.ROOM_TILE_NEGATIVE
SELF.C30.ROOM_TILE_NON_INTEGER
SELF.C31.ROOM_TILE_WRONG_LENGTH
```

## 13.4 独立画像

```text
SELF.D1.IMAGE_IDENTIFIER_UNRESOLVED
SELF.D2.IMAGE_CONSTRUCTION_MISSING
SELF.D3.IMAGE_SRC_MISSING
SELF.D4.IMAGE_SRC_AMBIGUOUS
SELF.D5.INVALID_BASE64
SELF.D6.NON_PNG
SELF.D7.TRUNCATED_PNG
SELF.D8.ZERO_OR_INVALID_DIMENSION
SELF.D9.ATLAS_IDENTIFIER_REUSED
SELF.D10.ATLAS_PAYLOAD_REUSED
SELF.D11.EXTERNAL_URL_USED
SELF.D12.ATLAS_RECT_REFERENCE_USED
```

## 13.5 v2凍結比較

```text
SELF.D13.SPR_RAW_SOURCE_CHANGED
SELF.D14.SPR_STRUCTURE_CHANGED
SELF.D15.SPR_HI_RAW_SOURCE_CHANGED
SELF.D16.ATLAS_SRC_STATEMENT_CHANGED
SELF.D17.ATLAS_PNG_CHANGED
SELF.D18.ATLAS_HI_SRC_CHANGED
SELF.D19.SPRAT_CHANGED
SELF.D20.DRAW_HERO_IMG_CHANGED
SELF.D21.BLIT_FUNCTION_CHANGED
SELF.D22.BLIT_FUNCTION_ADDED
SELF.D23.BLIT_FUNCTION_REMOVED
SELF.D24.DISK_HI_ATLAS_CHANGED
SELF.D25.DISK_HI_MANIFEST_BYTES_CHANGED
SELF.D26.DISK_HI_MANIFEST_STRUCTURE_CHANGED
```

各negative fixtureは、意図したcheck IDでfailしなければならない。

別checkerによる偶発的failだけではself-test成功としない。

次のpositive controlも必須とする。

- 正しい5ランドマーク集合
- lookoutを除いた正しいFOCUS_IMG
- TOWER 3画像
- 正しい3kind × 3LOD
- 正しいENEMY_WEAK
- 正しいROOM_SUBJ
- 正しい独立PNG
- v2と完全一致する凍結領域

self-test出力:

```text
tier_a_v3_selftest_report.json
```

---

# 14. Tier Aレポート契約

通常出力:

```text
tier_a_v3_report.json
```

最低限の構造:

```json
{
  "schema_version": 3,
  "mode": "verification",
  "checkpoint": {
    "tag": "tierA-lod-v3",
    "expected_commit": "5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f",
    "actual_commit": ""
  },
  "baseline": {
    "tag": "tierA-hero-fix-v2",
    "expected_commit": "13dbea7deec6e5994501ffc5e70b47e9d0e24dcf",
    "actual_commit": ""
  },
  "inherited_v2": {
    "atlas": {},
    "hero_direction": {}
  },
  "lod_tables": {},
  "independent_images": {},
  "frozen_regions": {},
  "checks": [],
  "summary": {
    "passed": 0,
    "failed": 0,
    "skipped": 0
  },
  "overall_status": "pass",
  "exit_code": 0
}
```

各check:

```json
{
  "id": "C5.FOCUS_IMG_KEYS",
  "status": "pass",
  "measured": {},
  "expected": {},
  "subjects": [],
  "message": ""
}
```

許可status:

```text
pass
fail
skip
```

mandatory checkを不都合な結果のために `skip` にしてはならない。

## 14.1 LODテーブル記録

各テーブルについて記録する。

```text
source span
actual keys
expected keys
missing keys
extra keys
normalized values
identifier references
unresolved references
known exceptions
```

## 14.2 独立画像記録

各意味スロットについて記録する。

```text
semantic slot
image identifier
PNG byte length
PNG SHA-256
RGBA SHA-256
width
height
Image construction count
src assignment count
atlas independence status
referencing table
```

## 14.3 凍結比較記録

各凍結対象について記録する。

```text
v2 SHA-256
v3 SHA-256
raw byte equality
parsed equality
PNG dimensions
RGBA equality
function inventory
first difference offset
```

---

# 15. Tier A exit code

```text
0:
  全mandatory checkがpass
  レポート書き込み成功

1:
  1件以上の不変条件fail

2:
  setup failure
  checkpoint failure
  dependency failure
  extraction failure
  internal exception
  report write failure
```

JSON内 `exit_code` とプロセスexit codeは一致しなければならない。

---

# 16. Tier A determinism

同じv2、v3、test harnessに対して:

- check順序が同じ
- table順序が同じ
- image順序が同じ
- function順序が同じ
- mismatch順序が同じ
- hashが同じ
- JSON key順序が同じ
- substantive report bytesが同じ

乱数を使用しない。

self-test fixtureにも乱数を使用しない。

時刻は合否、測定、レポートの実質内容に含めない。

---

# 17. Tier Bの位置づけ

Tier BはPlaywright TestとヘッドレスChromiumを標準とする。

使用可能な場合:

```text
Node.js
@playwright/test
既存のChromium／Chrome／Edge
```

受け入れ実行中に次を行ってはならない。

- npm install
- Playwright browser download
- Chromium download
- 外部CDNアクセス
- GitHubアクセス

Tier Bはオフライン起動する。

## 17.1 ブラウザ探索順

1. 既存Playwright Chromium
2. `PLAYWRIGHT_BROWSERS_PATH` で指定されたcache
3. 既存Google Chrome
4. 既存Microsoft Edge
5. `PW_CHROMIUM_EXECUTABLE` で指定されたChromium系実行ファイル

任意実行ファイルを使用した場合は、バージョンとパスをレポートする。

## 17.2 blocked条件

次の場合、Tier Bを `blocked` とする。

```text
browser-unavailable
playwright-unavailable
browser-version-incompatible
required-test-hook-missing
test-hook-version-incompatible
```

blocked時:

```text
exit code: 2
behavior gate: blocked
```

Tier Aは独立して実行し、合否を報告する。

---

# 18. Tier Bに必要な実装側フック

現 `master` にはseed、tick、moving、state取得のテストフックが存在しない。

また、乱数は次のように直接使用されている。

```text
d6():
  1 + floor(Math.random() * 6)

enemy damage:
  min + floor(Math.random() * range)
```

Tier B実行前に、Claude Codeは乱数呼び出しを単一の `rng()` 経路へ集約する必要がある。

## 18.1 有効化条件

テストフックは次のquery parameterがある場合だけ有効にする。

```text
?pwtest=1
```

通常起動時は、テスト用グローバル関数が存在してはならない。

## 18.2 必須フック

最低限、次を提供する。

```javascript
window.__setSeed(seed)
window.__setTick(tick)
window.__setMoving(moving)
window.__freezeTick(frozen)
window.__advanceTicks(count)
window.__state()

window.__setupLandmark(subject)
window.__setupBattle(options)
window.__finishBattle(outcome)
```

## 18.3 RNG

`window.__setSeed(n)` は、32bit整数seedで決定論的PRNGを初期化する。

test modeでは、すべてのゲーム乱数がこのPRNGを通る。

対象:

```text
d6
敵ダメージ
命中判定
逃走判定
その他のMath.random使用箇所
```

`Math.random()` の直接呼び出しが残っていてはならない。

`__state()` は最低限次を返す。

```text
rngSeed
rngState
rngDrawCount
```

LODを開く、閉じる、画像を見る、弱点を見るだけでは `rngDrawCount` が変化してはならない。

## 18.4 tick／moving

```javascript
window.__setTick(n)
window.__setMoving(boolean)
window.__freezeTick(boolean)
window.__advanceTicks(n)
```

要件:

- `__freezeTick(true)` 中は実時間loopで `S.tick` が増えない
- `__advanceTicks(n)` だけが明示的にtickを進める
- `S.moving` を固定できる
- テストは原則として固定時間待機に依存しない

## 18.5 状態取得

`window.__state()` は読み取り専用snapshotを返す。

最低限:

```javascript
{
  mode,
  lod,
  tick,
  moving,

  focusSubject,
  towerKey,
  roomSubject,

  msgShown,
  msgLod,
  messageText,

  taken,
  effects: {
    physDmg,
    hitAll,
    recon,
    hitChief,
    herbs
  },

  rngSeed,
  rngState,
  rngDrawCount,

  battle: {
    active,
    phase,
    commandMode,
    turnSerial,
    enemyActionCount,
    selectedEnemyIndex,
    selectedEnemyKind,
    detailLod,
    overlayVisible,
    party,
    foes
  }
}
```

返却値を変更してもゲーム状態が変化しないよう、deep copyまたは同等の読み取り専用値にする。

## 18.6 ランドマークfixture

```javascript
window.__setupLandmark(subject)
```

許可subject:

```text
well
shrine
lookout
elder
herb
```

準備する状態:

- 該当ランドマークの入口条件を満たす
- LOD 0
- 未取得
- 既定効果値
- `msgShown=false`
- `msgLod=null`
- `moving=false`
- 固定tick
- 固定seed

fixture準備後のLOD操作、Z入力、イベント取得は製品の通常入力経路を使用する。

## 18.7 戦闘fixture

```javascript
window.__setupBattle(options)
```

例:

```javascript
{
  encounter: "sentry-single",
  seed: 1
}
```

または:

```javascript
{
  foes: ["chief", "goblin"],
  seed: 1
}
```

最低限、次を再現できなければならない。

```text
sentry単体
goblin×2
chief+goblin
```

fixture準備後の対象選択、LOD操作、攻撃入力は製品の通常経路を使用する。

## 18.8 戦闘終了fixture

```javascript
window.__finishBattle(outcome)
```

outcome:

```text
win
wipe
flee
```

このフックはproductionの戦闘終了handlerを呼ぶだけとする。

フック自身がDOMを直接消去してはならない。

---

# 19. Tier B安定DOM契約

対象HTMLに次の `data-testid` を付与する。

```text
zoom-in
zoom-out
lod-value
lod-event-message

focus-image
tower-image
room-image
npc-image

battle-command-panel
battle-target-list
battle-target-option

enemy-detail-overlay
enemy-detail-image
enemy-hp-number
enemy-hp-bar
enemy-weakness

party-hp
```

複数要素には必要に応じて次を付与する。

```text
data-subject
data-kind
data-index
data-lod
data-image-id
```

Tier Bは不安定なCSS階層や描画座標だけに依存しない。

---

# 20. Tier B共通実行設定

```yaml
browser: chromium
headless: true
workers: 1
retries: 0
viewport:
  width: 1280
  height: 960
deviceScaleFactor: 1
locale: ja-JP
timezoneId: UTC
colorScheme: light
```

外部通信は禁止する。

対象ページは原則として次で開く。

```text
file:///.../index.html?pwtest=1
```

file URLに制約がある場合は、Python標準ライブラリでlocal serverを起動してよい。

```text
127.0.0.1のみ
外部bind禁止
```

ページロード後、次を確認する。

- 必須テストフックが存在
- `__state()` が呼べる
- RNG seedが設定できる
- tickをfreezeできる
- 外部requestが0件

---

# 21. Tier B: ランドマークシナリオ

対象:

```text
well
shrine
lookout
elder
herb
```

各subjectはfresh resetまたはfresh browser contextで検査する。

## L1. 拡大遷移

各subjectについて:

```text
LOD 0
→ +拡大
LOD 1
→ +拡大
LOD 2
→ +拡大
LOD 3
```

各段階で:

- `lod` が期待値
- subjectが維持される
- movingがfalse
- 予期しないmode遷移がない

## L2. 縮小遷移

LOD 3から:

```text
3 → 2 → 1 → 0
```

1段ずつ戻らなければならない。

飛び越し、対象喪失、縮小不能はfail。

## L3. +3 DOM画像

LOD 3で、対応画像がcanvasだけでなくDOM `<img>` 経路で表示されることを確認する。

共通条件:

- visible
- `complete == true`
- `naturalWidth > 0`
- `naturalHeight > 0`
- bounding boxの幅と高さが正
- srcがインラインPNG
- PNG hashがTier A reportと一致
- `data-image-id` が解決済み意味スロットと一致

lookoutでは:

```text
TOWER_VIEW
```

を使用し、次も確認する。

```text
#focusImg.full相当
object-fit: cover
full-bleed経路
```

「原寸」は、元PNGがDOM Imageとして正常decodeされ、natural sizeを保持していることを意味する。

CSS上の表示幅とnatural widthの完全一致は要求しない。

## L4. 効果取得

fresh未取得状態のLOD 3でZを押す。

期待効果:

```yaml
well:
  field: physDmg
  delta: 2

shrine:
  field: hitAll
  delta: 1

lookout:
  field: recon
  transition: false_to_true

elder:
  field: hitChief
  delta: 2

herb:
  field: herbs
  delta: 2
```

assert:

- 対応取得状態がfalseからtrue
- 対応効果だけが正確に1回変化
- 他効果は不変
- `rngDrawCount` 不変
- `msgShown == true`
- `msgLod == current lod`

## L5. 二重取得防止

同じランドマークで再度Zを押す。

assert:

- 取得状態不変
- 全効果不変
- 初回取得文言を再表示しない
- 表示文言が `TAKEN_MSG[subject]` と一致
- `msgShown == true`
- `msgLod == current lod`

## L6. +2から+3へのメッセージ消去

fresh状態で:

1. LOD 2へ移動
2. Zを押す
3. メッセージ表示を確認
4. LOD 3へ移動

assert:

- LOD 2のmessageがDOMに残らない
- `msgShown` が新LOD状態と整合
- `msgLod` が2のまま残らない
- LOD 3で再度Zを押すと取得済み文言
- 効果の二重付与なし

## L7. +3から+2へのメッセージ消去

逆方向も同様に検査する。

```text
LOD 3でZ
→ LOD 2へ縮小
```

LOD 3のtransient messageをLOD 2へ持ち越してはならない。

## L8. msgShown／msgLod一般則

transient event messageがvisibleな時:

```text
msgShown == true
msgLod == current lod
```

LOD変更後:

```text
previous message text not visible
previous msgLod not retained as active message
```

静的caption、`FOCUS_CAP`、`FOCUS_TXT` はtransient event messageとして扱わない。

---

# 22. Tier B: 戦闘LODシナリオ

## M1. 単体戦

単体戦は `sentry` encounterで検査する。

開始時:

```text
B.foes.length == 1
foe.kind == sentry
hp == 5
atk == 0
dmg == [1,2]
target == 6
```

LOD +1から+2へ拡大した時:

- 対象選択画面を出さない
- sentryを自動対象にする
- selectedEnemyIndex == 0
- +2へ移行する

## M2. 複数戦

次の双方を検査する。

```text
goblin×2
chief+goblin
```

LOD +1から+2へ拡大する時:

- 対象選択リストが表示される
- 選択完了までLOD +1を維持する
- 生存敵ごとの選択肢が表示される
- 選択した敵がselected targetになる
- +2／+3で選択対象の画像と情報を表示する

`goblin×2` では、同kindであってもindex別に選択できなければならない。

`chief+goblin` では、異なるkindを個別に選択できなければならない。

## M3. +1 HP表示

LOD +1:

- 味方HP visible
- 味方HPがstateと一致
- 敵HP数値 hidden
- 敵HPバー hidden
- 弱点 hidden
- 戦闘コマンドpanel使用可能

## M4. +2敵詳細

対象選択後のLOD +2:

- enemy detail overlay visible
- DOM enemy `<img>` visible
- `ENEMY_IMG[kind][2]` のhashと一致
- HP数値 visible
- HP数値がstateと一致
- HPバー visible
- HPバー最大値がmax HPと一致
- HPバー現在値がcurrent HPと一致
- 弱点 hidden

HPバー比率の許容差:

```text
1 percentage point以内
```

## M5. +3敵詳細

LOD +3:

- `ENEMY_IMG[kind][3]` の画像
- HP数値 visible
- HPバー visible
- 弱点 visible

弱点期待値:

```yaml
goblin: まほう
sentry: たたかう(物理)
chief: まほう
```

ラベルのcolonは次を許可する。

```text
弱点: まほう
弱点：まほう
```

colonと周辺空白を正規化した後、値本体を完全一致で比較する。

## M6. ターン凍結

LOD +2と+3の双方で検査する。

進入直後に保存:

```text
turnSerial
enemyActionCount
party HP
全enemy HP
battle phase
selected target
rngDrawCount
```

その後:

```javascript
__advanceTicks(300)
```

assert:

- turnSerial不変
- enemyActionCount不変
- party HP不変
- 全enemy HP不変
- battle phase不変
- selected target不変
- rngDrawCount不変

描画用 `S.tick` の明示的変化だけは許可する。

## M7. 縮小復帰

LOD +3から:

```text
+3 → +2 → +1
```

LOD +1へ戻った時:

- detail overlay hidden
- enemy image hidden
- weakness hidden
- HP詳細 hidden
- battle command panel visible
- コマンド入力可能
- 戦闘自体は継続
- 一時detail target状態が解放される

## M8. LOD表示によるRNG非消費

各kindについて:

```text
+1 → +2 → +3 → +2 → +1
```

だけを実行する。

開始時と終了時で:

```text
rngDrawCountが同じ
rngStateが同じ
```

でなければならない。

## M9. 弱点表示が戦闘計算へ影響しない

各kind、各攻撃種別についてcontrolとinspectedを比較する。

攻撃種別:

```text
たたかう
まほう
```

対象kind:

```text
goblin
sentry
chief
```

合計:

```text
3 kinds × 2 actions = 6 comparisons
```

### control

```text
同じseed
同じ初期状態
LOD詳細を開かない
指定攻撃を実行
```

### inspected

```text
同じseed
同じ初期状態
+2を開く
+3を開く
弱点を見る
+1へ戻る
controlと同じ攻撃を実行
```

比較:

```text
hit/miss
damage
target HP delta
rng draw count
rng draw sequence
turnSerial
enemy response
party HP delta
status change
```

すべて一致しなければならない。

弱点文字列は表示専用であり、ダメージ、命中、敵選択、乱数消費へ影響してはならない。

## M10. 敵基礎値

fresh fixture開始時に次を確認する。

```yaml
goblin:
  hp: 5
  atk: 0
  dmg: [1, 2]
  target: 6

sentry:
  hp: 5
  atk: 0
  dmg: [1, 2]
  target: 6

chief:
  hp: 18
  atk: 2
  dmg: [2, 5]
  target: 8
```

Tier Aで抽出した静的値とTier Bのruntime stateが一致しなければならない。

## M11. 終了時クリーンアップ

次のoutcomeを検査する。

```text
win
wipe
flee
```

LODレベル:

```text
+2
+3
```

組合せ:

```text
3 outcomes × 2 LOD levels = 6
```

敵詳細オーバーレイを表示したままproduction outcome handlerを実行する。

assert:

- enemy detail overlay hiddenまたはDOMから除去
- enemy image hiddenまたは除去
- weakness hiddenまたは除去
- HP詳細 hiddenまたは除去
- selected detail targetがnull
- detail LOD状態解除
- outcome固有modeへ遷移
- 旧敵画像が次画面へ残らない
- 再開後にoverlayが復活しない

---

# 23. Tier B helper sanity test

Tier B helper自身について最低限次を確認する。

```text
存在しないtest IDはfailする
画像hashの1文字差を検出する
HP差を検出する
message差を検出する
turnSerial差を検出する
rngDrawCount差を検出する
```

これらは対象ゲーム状態を壊さないhelper unit testとして実行する。

---

# 24. Tier Bレポート

出力:

```text
tier_b_v3_report.json
```

最低限:

```json
{
  "schema_version": 3,
  "checkpoint": {
    "tag": "tierA-lod-v3",
    "expected_commit": "5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f",
    "actual_commit": ""
  },
  "tier_a_report": {
    "path": "",
    "sha256": "",
    "status": "pass"
  },
  "environment": {
    "node_version": "",
    "playwright_version": "",
    "browser_product": "",
    "browser_version": "",
    "browser_executable": "",
    "resolution_method": "",
    "external_requests": []
  },
  "hooks": {
    "status": "available",
    "missing": []
  },
  "scenarios": [],
  "summary": {
    "passed": 0,
    "failed": 0,
    "skipped": 0,
    "blocked": 0
  },
  "overall_status": "pass",
  "exit_code": 0
}
```

各scenario:

```text
scenario ID
subjectまたはenemy kind
encounter
seed
actions
before state
after state
DOM evidence
image hash
expected
actual
status
message
```

failure時の診断用に、スクリーンショットとPlaywright traceを保存してよい。

pixel screenshot比較は合否条件にしない。

---

# 25. Tier B exit code

```text
0:
  Tier Bを実行でき
  全behavior invariantがpass

1:
  1件以上のbehavior invariant fail

2:
  browser unavailable
  Playwright unavailable
  test hook不足
  setup failure
  browser incompatibility
  internal exception
  report write failure
```

`blocked` はexit 2を使用する。

Codexはexit 2をpassと報告してはならない。

---

# 26. 総合判定

## 26.1 完全合格

```text
Tier A: pass / exit 0
Tier B: pass / exit 0
```

```text
static gate: pass
behavior gate: pass
overall certification: full-pass
```

## 26.2 Tier B blocked

```text
Tier A: pass / exit 0
Tier B: blocked / exit 2
```

blocked理由が次のいずれかの場合:

```text
browser-unavailable
playwright-unavailable
required-test-hook-missing
```

```text
static gate: pass
behavior gate: blocked
overall certification: partial-static-pass
```

この結果を「Tier A/B完全合格」と表現してはならない。

## 26.3 Tier B behavior fail

```text
Tier A: pass
Tier B: fail / exit 1
```

```text
overall certification: fail
```

## 26.4 Tier A fail

Tier B結果にかかわらず:

```text
overall certification: fail
```

---

# 27. Codex実行手順

## 27.1 ローカルタグ確認

ネットワークを使用せず、既存ローカルrepositoryを使う。

```powershell
cd C:\Users\pipe_render\perceptive-world-demo

git show-ref --tags tierA-hero-fix-v2
git show-ref --tags tierA-lod-v3
```

## 27.2 v2 worktree

```powershell
git worktree add --detach `
  C:\Users\pipe_render\perceptive-world-demo-v2-baseline `
  tierA-hero-fix-v2
```

## 27.3 v3 worktree

```powershell
git worktree add --detach `
  C:\Users\pipe_render\perceptive-world-demo-v3-target `
  tierA-lod-v3
```

## 27.4 harness確認

```powershell
cd C:\Users\pipe_render\perceptive-world-demo-v3-tests

git branch --show-current
git status --porcelain
```

期待branch:

```text
test/tier-a-v3
```

## 27.5 実行前integrity

```powershell
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline rev-parse HEAD
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline describe --tags --exact-match HEAD

git -C C:\Users\pipe_render\perceptive-world-demo-v3-target status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target rev-parse HEAD
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target describe --tags --exact-match HEAD
```

## 27.6 Tier A self-test

```powershell
Remove-Item .\tier_a_v3_selftest_report.json -ErrorAction SilentlyContinue

python tests\tier_a.py --selftest
$tierASelfExit = $LASTEXITCODE

Write-Output "TIER_A_SELFTEST_EXIT=$tierASelfExit"
```

## 27.7 Tier A通常検証

```powershell
Remove-Item .\tier_a_v3_report.json -ErrorAction SilentlyContinue

python tests\tier_a.py `
  --baseline-root C:\Users\pipe_render\perceptive-world-demo-v2-baseline `
  C:\Users\pipe_render\perceptive-world-demo-v3-target

$tierAExit = $LASTEXITCODE

Write-Output "TIER_A_EXIT=$tierAExit"
```

Tier Aが非0でもレポートを保存し、失敗checkを報告する。

## 27.8 Tier B環境probe

```powershell
node --version
npx playwright --version
```

この段階でinstallやdownloadを実行しない。

既存Playwright browser cache:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = "<existing-cache>"
```

既存Chromium系ブラウザ:

```powershell
$env:PW_CHROMIUM_EXECUTABLE = "<existing-browser-path>"
```

## 27.9 Tier B実行

Tier Aがpassした場合に実行する。

```powershell
Remove-Item .\tier_b_v3_report.json -ErrorAction SilentlyContinue

$env:PW_TARGET_ROOT = `
  "C:\Users\pipe_render\perceptive-world-demo-v3-target"

$env:PW_TIER_A_REPORT = `
  "C:\Users\pipe_render\perceptive-world-demo-v3-tests\tier_a_v3_report.json"

npx playwright test --config=playwright.config.mjs
$tierBExit = $LASTEXITCODE

Write-Output "TIER_B_EXIT=$tierBExit"
```

Chromiumまたはhookが利用できない場合、テストや対象を変更せず、`blocked` レポートを出力する。

## 27.10 実行後integrity

v2とv3双方について再確認する。

```powershell
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline rev-parse HEAD

git -C C:\Users\pipe_render\perceptive-world-demo-v3-target status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target rev-parse HEAD
```

実行前後でcleanとHEADが一致しなければならない。

---

# 28. Codex報告形式

```markdown
# Tier A/B v3 Execution Report

## Checkpoints

- v2 baseline tag:
- v2 baseline SHA:
- v3 target tag:
- v3 target SHA:
- v2 clean before:
- v2 clean after:
- v3 clean before:
- v3 clean after:

## Tier A self-test

- Command:
- Exit code:
- Overall status:
- Passed:
- Failed:
- Report:

## Tier A verification

- Command:
- Exit code:
- Overall status:
- Inherited v2 atlas checks:
- Inherited v2 hero checks:
- LOD table checks:
- Independent image checks:
- Frozen-region checks:

## Tier A failures

### `<check ID>`

- Expected:
- Actual:
- Subject/table/image:
- Message:

失敗がない場合:

- None

## Tier B environment

- Node version:
- Playwright version:
- Browser status:
- Browser product:
- Browser version:
- Executable:
- Resolution method:
- Required hooks:
- Missing hooks:
- External network requests:

## Tier B verification

- Command:
- Exit code:
- Overall status:
- Landmark passed/failed:
- Battle passed/failed:
- Failed scenario IDs:
- Blocked reason:

## Gate verdict

- Static gate:
- Behavior gate:
- Overall certification:
- Browser-unavailable exception:
- Hook-unavailable exception:

## Reports

- tier_a_v3_selftest_report.json:
- tier_a_v3_report.json:
- tier_b_v3_report.json:

## Integrity

- Target files modified:
- Baseline files modified:
- Test files modified during execution:
- Network used:
- Browser download attempted:
- Unexpected exceptions:
```

---

# 29. 凍結定数

```yaml
checkpoint:
  tag: tierA-lod-v3
  commit: "5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f"

baseline:
  tag: tierA-hero-fix-v2
  commit: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

harness:
  branch: test/tier-a-v3
  included_in_target: false

landmarks:
  ordered:
    - well
    - shrine
    - lookout
    - elder
    - herb

focus:
  full_key_tables:
    - FOCUS_CAP
    - FOCUS_TXT
    - FOCUS_EVENT
    - TAKEN_MSG

  full_keys:
    - well
    - shrine
    - lookout
    - elder
    - herb

  image_keys:
    - well
    - shrine
    - elder
    - herb

  image_exception:
    key: lookout
    reason: dedicated drawTower/towerKey sequence
    images:
      - TOWER_FULL
      - TOWER_TOP
      - TOWER_VIEW

enemy:
  kinds:
    - goblin
    - sentry
    - chief

  lod_levels:
    - 1
    - 2
    - 3

  weakness:
    goblin: まほう
    sentry: たたかう(物理)
    chief: まほう

  base_stats:
    goblin:
      hp: 5
      atk: 0
      dmg: [1, 2]
      target: 6

    sentry:
      hp: 5
      atk: 0
      dmg: [1, 2]
      target: 6

    chief:
      hp: 18
      atk: 2
      dmg: [2, 5]
      target: 8

room_subjects:
  keys:
    - elder
    - herb

  required_fields:
    - room
    - npcImg
    - tile

effects:
  well:
    field: physDmg
    delta: 2

  shrine:
    field: hitAll
    delta: 1

  lookout:
    field: recon
    transition: false_to_true

  elder:
    field: hitChief
    delta: 2

  herb:
    field: herbs
    delta: 2

independent_images:
  semantic_slot_count: 20

  groups:
    focus: 4
    tower: 3
    room_and_npc: 4
    enemies: 9

frozen_v2_regions:
  index_html:
    - SPR declaration
    - SPR_HI declaration
    - ATLAS.src assignment
    - ATLAS_HI.src assignment
    - sprAt function
    - drawHeroImg function
    - all top-level function names matching ^blit

  committed_files:
    - assets/hi/atlas_hi.png
    - assets/hi/manifest_hi.json

tier_a:
  dependencies:
    - Python 3
    - Pillow
    - numpy
    - standard library
    - read-only Git

  exit_codes:
    pass: 0
    invariant_failure: 1
    setup_failure: 2

tier_b:
  framework: Playwright
  browser: Chromium
  headless: true
  workers: 1
  retries: 0
  mandatory_when_available: true
  blocked_allowed_when_unavailable: true

  exit_codes:
    pass: 0
    behavior_failure: 1
    blocked_or_setup_failure: 2

test_hooks:
  activation: "?pwtest=1"

  required:
    - window.__setSeed
    - window.__setTick
    - window.__setMoving
    - window.__freezeTick
    - window.__advanceTicks
    - window.__state
    - window.__setupLandmark
    - window.__setupBattle
    - window.__finishBattle

reports:
  tier_a_selftest: tier_a_v3_selftest_report.json
  tier_a: tier_a_v3_report.json
  tier_b: tier_b_v3_report.json
```

---

# 30. 変更管理境界

本書の承認により、次を凍結する。

- v2 A／B checkerの継承
- hero方向閾値
- 必須34 sprite
- 5ランドマーク集合
- `FOCUS_CAP`／`FOCUS_TXT`／`FOCUS_EVENT` のキー集合
- `FOCUS_IMG` からlookoutを除く例外
- `TOWER_FULL`／`TOWER_TOP`／`TOWER_VIEW`
- `TAKEN_MSG` 5キー
- 敵3kind
- 敵LOD 1〜3
- 敵基礎値
- 弱点文字列
- `ROOM_SUBJ` 2キー
- 独立Image構造
- 20画像意味スロット
- v2凍結領域のbyte一致
- C／D negative self-test
- Tier A report／exit code／determinism
- Tier B required hook能力
- ランドマークシナリオ
- 単体／複数戦シナリオ
- 詳細表示中のターン凍結
- 弱点表示のみの比較方法
- 勝利／全滅／逃走クリーンアップ
- Codex環境でのTier B blocked切り分け
- Codex実行手順
- 総合合否モデル

承認後、実測結果に合わせて条件を緩和してはならない。

次を変更する場合は、preregistration revisionと再承認が必要である。

- `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f` 以外のチェックポイント条件
- LODテーブル名
- キー集合
- lookout例外
- 敵基礎値
- 弱点値
- イベント効果
- 独立画像アーキテクチャ
- v2凍結比較対象
- テストフックAPI
- Tier Bシナリオ
- 合否境界
