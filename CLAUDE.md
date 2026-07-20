# CLAUDE.md — Perceptive World / Visual Demo（見た目デモ）

> Claude Code への引き継ぎメモ。**見た目（グラフィックス）の方向性を認識合わせするための2Dデモ**リポジトリ。
> 派生元は決定論的TRPGエンジン `perceptive-world`（`feature/chatgpt-implementation`／ChatGPT設計・Codex実装）だが、
> 本リポジトリは**独立**しており、エンジン本体 `trpg_core` は持たない。`design/` のゲームデータ・視覚基準のみ引き継ぐ。
> コードを読めば分かることは省き、背景・設計意図・全体像・注意点に絞る。

---

## 0. 進行中の作業（最優先の引き継ぎタスク）★これを実装したい

**やりたいこと**: ズームの「詳細度+2」で表示されるドット絵を、より高精細な画像に置き換える。
高精細プロンプトで **Nano Banana（画像生成）から出力した画像**を用意済み。これを詳細度+2の描画に適用する。

**用意した新素材（`assets/source/` に配置）** — Nano Banana 出力、1024×1024:
- 主人公: 3×3グリッド（歩行フレーム／緑チュニック・茶髪 → 既存 `hero_*` に対応）
- 地形: 2×2グリッド（左上=草地 / 右上=土 / 左下=水 / 右下=花畑 → `grass/dirt/water/flower`）
- 井戸（`well`）／木（`tree`）

**現状の重要な前提（必読）**:
`index.html` の `draw()` 高詳細パスは、アトラス読込済み（`ASSETS.ready`）だと**詳細度+2でも既存64px素材を単純拡大しているだけ**で、
真の高精細画像は未使用。手続き描画 `drawTileHi2 / grass64 / tree64 / well64 / drawHeroHi2`（HTML 347〜428行付近）は
**アトラス未読込時のフォールバック専用**。本タスクは「**詳細度+2(`S.lod>=2`)のときだけ参照する“第2の高精細アセット群”を新設**」する改修。
新素材のカバー範囲（草/土/水/花/木/井戸/主人公）は、詳細化対象タイル（＝井戸周辺ズーム）とちょうど一致。

**実装方針（候補）**:
1. `assets/source/` の新素材を `tools/conform.py` で切出し・透過し、**高精細アトラス `assets/hi/atlas_hi.png` ＋ `manifest_hi.json` を生成**
   （既存 conform.py を流用。ただし入力パスと**64pxに縮小せず大きいまま出力**する点を変更）。
2. `index.html` に高精細スプライト表 `SPR_HI` と画像 `ATLAS_HI` を追加。
3. `draw()` の高詳細分岐（650〜672行付近、`hi2 = S.lod>=2`）と `drawTileImg/drawHeroImg` を、
   `S.lod>=2` のとき `SPR_HI/ATLAS_HI` を参照するよう分岐追加。対象タイル（`grass/dirt/water/flower/tree/well/hero_*`）のみ差替え、未対応は従来拡大にフォールバック。
4. 村の井戸付近で `＋ズームイン`×2 → 詳細度2 で、拡大ボケが新素材の高精細ドット絵に置き換わることを目視確認。

**視覚基準**: 画風・キャラの一貫性は `design/visual_bible.yaml`、プロンプトは `design/image_prompts.yaml` に従う。
派生元の正準LODアセット `assets/reference/two_d/goblin/*/lod0〜3.png`（lod2=64×64）は**見た目のレンジ参照**として使う。

> ※ 単一HTML配布を保つ場合、新素材は Base64 で `index.html` に埋め込む（アトラス化して1枚にまとめると差分が小さい）。
> 外部ファイル読込に変えてよいかは実装時に確認（現状は単一HTMLで完結）。

---

## 1. デモ本体の概要（index.html）

- ファミコン／SFC風 2D RPG。内部解像度 256×224 の単一 `<canvas>`、素の JavaScript（フレームワークなし）。
- 単一HTMLで完結（HTML＋CSS＋JS＋Base64スプライトアトラスを同梱）。ブラウザで開けば動く。
- 中核コンセプト＝「知覚(perceptive)」: 戦う前の**準備／情報収集（最大3つ）**が戦闘・判定にボーナスを与える。
- 判定: 2D6＋修正。合計12=会心、2=ファンブル、目標値以上で成功。

### 描画バックエンド
`blit()/blitFlip()/blitAnchor()` がアトラスから矩形を切出し描画。アトラス未読込時のフォールバックとして
手続き的ドット絵（`grass()/tree()/well()` 等、16px版・拡大版が併存）も残る。

### タイル文字の凡例（マップはコードで文字グリッド生成）
```
,草地  =道  T木  w水  "花  #壁  ^屋根  dドア(warp)
O井戸  K物見櫓  E村長  A薬草の女  H祠  G森の門
.洞窟床  x洞窟壁  <洞窟出口  i松明  F室内床  %室内壁
```
`BLOCK`=進入不可、`EVENT`=調べると反応、`warps`=マップ間ワープ。

### 状態・シーン・ループ
- グローバル `S`（scene/map/player/hp/mp/bonus/prep/visited…）が唯一の状態源。戦闘は `B`。
- `S.scene`: `title|map|dialogue|battle|win|over`。`draw()` と入力がシーン別に分岐。
- メインループ `loop()`（rAF）で `S.tick++` → 移動更新 → `draw()`。入力は `KMAP`＋`keyPress()/battleKey()`、タッチは `bindTouch()`。

### 準備(prep)システム＝本作の肝
`interact()`→`eventPrep()` で村長/薬草の女/祠/井戸/物見櫓を調べると `S.prep`＋（最大 `prepMax=3`）、
`S.bonus`（`hitAll/hitChief/physDmg/recon`）や薬草が増え、後の戦闘・`bushCheck()/caveSneak()` の判定に加算される。
値は `design/scenario-goblin.yaml` と一致（村長=頭目命中+2 / 薬草×2 / 祠=全命中+1 / 井戸=物理+2）。

### 戦闘
`startBattle()`→コマンド（たたかう/まほう/くすり/にげる）。命中 `rollDice(mod,target)`=2D6+修正。
ヒーロー能力値 `HERO_STR=8,HERO_MAG=8,HERO_VIT=9`。物理=`d6+STR修正+physDmg`、魔法=`d6+3+MAG修正`、会心で2倍。
敵 goblin/sentry/chief(ボス)。ボス撃破→win、全滅→over（村で半分HP回復）。

### ズーム／LOD
`S.lod`(0〜2)で井戸周辺のみ詳細度アップ（`zoomIn/zoomOut/nearWell/checkLodExit`）。16→32→64px 切替、`#screen.hi` でUIをFF風青窓に。**現状は井戸近傍限定の部分実装**。★§0のタスク対象。

## 2. マップ構成
- 村(village 22×18): 中央広場スタート、西=村長宅／東=薬草小屋（室内へワープ）、井戸・物見櫓・祠・森の門。
- 室内(interior 11×9): `props` 配列で家具配置、`blockSet` で衝突。
- 洞窟(cave): 見張りは「たたかう／しのび足で回避(vit判定)」の選択式。奥に頭目。

## 3. 素材パイプライン（tools/conform.py）
AI生成シート → 背景透過・切出し・リサイズ → `atlas.png`＋`manifest.json` を出力。
**入出力パスが派生元環境（`/mnt/user-data/uploads`＋UUID名）依存**なので、ローカルで動かすには `U=` と `find()` を
`assets/source/` の実ファイル名に合わせて要修正。§0では「64pxへ縮小しない高精細版」出力の追加が要る。

## 4. 引き継ぎ時の注意（次の作業候補）
- conform.py の入出力パス依存を修正（最初の一手）。
- 詳細度+2の高精細化（§0）が最優先。
- 手続き描画（`*Hi`/`*64`）とアトラス描画が二重存在。アトラス運用一本化なら整理余地。
- 素材差替え時は SPR(manifest) と atlas の両方を同期（conform.py 再生成が安全）。
- 戦闘RNGは `Math.random()` 直。派生元エンジンは決定論的だが、本デモは非決定論。リプレイ性が要るなら別途検討。

## 5. Git 運用メモ
- 本リポジトリは派生元とは**独立**（upstream リンクなし・履歴リセット）。派生元の更新取り込みは手動コピー。
- コミットは対象ファイルを明示（`git add .` を避ける）。生成物（`assets/hi/` の出力等）は必要に応じ `.gitignore` 管理。

---
_初版: 2026-07-20。派生元 perceptive-world@feature/chatgpt-implementation の design/ 引き継ぎ＋見た目デモHTML。_
