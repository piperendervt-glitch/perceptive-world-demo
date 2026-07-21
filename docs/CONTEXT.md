# perceptive-world-demo — プロジェクト引き継ぎコンテキスト

別のチャット／エージェントがこのプロジェクトを引き継ぐための全体像メモ。
現状（HEAD `5d770c3`）の実コードに基づく。

> 注意: 直近の push 報告では SHA `3f4d3a1` とあったが、clone した main の実 HEAD は
> `5d770c3`（enemy コミット、embed_enemy.py 込み）。引き継ぎ時はまず
> `git -C <repo> rev-parse HEAD` で最新を確認すること。

---

## 1. プロジェクト概要

- **目的**: 2D 見下ろし JRPG の「見た目デモ」。ゲーム性より、Nano Banana 生成のドット絵を
  段階的な詳細度（LOD）で見せる仕組みが主眼。
- **構成**: 単一ファイル `index.html`（vanilla JS + canvas）。スプライトはインライン base64。
- **リポジトリ**: https://github.com/piperendervt-glitch/perceptive-world-demo
- **ローカル**: `C:\Users\pipe_render\dev\pw-work\perceptive-world-demo`（main が正ブランチ）
- **言語**: 会話・ドキュメント・UI 文言は日本語。コード識別子は英語。

## 2. 多エージェント運用（役割分担）

- **Nano Banana**（画像生成）: マゼンタ背景のドット絵を生成。プロンプトは統括側が用意。
- **Claude Code**（実装・コミット）: index.html 編集、build/embed スクリプト、git 操作。
  「凍結対象のバイト不変」を毎回 assert して報告する規律。
- **Codex**（独立テスト実行）: Tier A を凍結タグに対して実行し合否報告（実装者と分離）。
- **統括レビュー**（このチャットの役割）: 画像の実測、要件の確定、実装依頼文の作成、
  実装レビュー、非回帰の確認。

依頼の型: 統括が「実装依頼文（変更箇所・変更禁止・検証項目つき）」を書く → Claude Code が
実装＋自己検証報告 → 統括がレビュー → コミット。画像は「生成 → 実測 → 実装依頼」の順。

## 3. index.html アーキテクチャ（重要な二分法）

スプライトは2系統ある。**この区別が設計の背骨**。

- **アトラス系（凍結対象）**: `SPR`/`ATLAS`（base、詳細度0/+1）と `SPR_HI`/`ATLAS_HI`
  （HI、詳細度+2の井戸付近ズーム）。hero・地形・既存プロップ・雑魚敵スプライト等。
  **Tier A の検査対象**。原則ここは触らない。
- **独立インライン画像（アトラス外）**: 詳細度の +2/+3 やランドマーク／敵のクローズアップ。
  `WELL_FOCUS`/`ELDER_ROOM`/`ENEMY_IMG` 等の個別 `Image` として base64 インライン化。
  アトラスに入れないので **hero/base/HI・Tier A に影響しない**。

> 設計原則: **新しい詳細度コンテンツは必ずアトラス外の独立画像で足す**。これにより
> hero とアトラス整合が常に不変＝ Tier A 凍結ガードが素通りせず生き続ける。

## 4. 詳細度（LOD）システム

`MAXLOD=3`。詳細度 0/+1/+2/+3 の意味と入口は「対象」ごとに異なる。

### 対象と入口条件

| 対象 | +0 | +1 | +2 | +3 |
|---|---|---|---|---|
| 井戸 well (9,3) | 村マップ | 井戸付近ズーム(base) | 井戸付近ズーム(HI) | 黒背景に井戸大写し(focus) |
| 祠 shrine (10,12) | 村マップ | 同上 | 同上(HI shrine) | 祠 focus |
| 物見櫓 lookout/'K' (4,3) | 村マップ | 櫓下シーン(tower_full) | 見張り台シーン(tower_top) | 森の遠望(tower_view) |
| 村長 elder (室内 5,2) | 村マップ | 既存室内マップ(扉ワープ) | 室内+村長ちび+歩行(ROOM_SUBJ) | 村長全身 focus |
| 薬師 herb (室内 5,2) | 村マップ | 既存室内マップ | 室内+薬師ちび+歩行 | 薬師全身 focus |
| モンスター(戦闘) | フィールド | 戦闘画面(敵HP非表示) | 対象敵の中間画像+HP+バー | 対象敵の精細画像+弱点 |

- 井戸/祠: 村マップの近接ズーム（`nearWell`/`nearShrine`, 半径 `WELLR=SHRINER=3`）。
- 櫓: 近接 or 正面で上キー（登攀）→ 専用シーン。`nearTower`（`TOWERR=1`）。
- 村長/薬師: 扉ワープで室内(+1、既存)→ NPC 付近で +拡大 → +2 専用シーン。
- 戦闘: 対象選択（複数敵時）or 自動（単体）→ +拡大で +2/+3。`battleZoomIn/Out`, `ENEMY_MAXLOD=3`。

### 中核テーブル（index.html）

- `FOCUS_IMG = {well, shrine, elder, herb}` … +3 focus 画像（`lookout` は tower 専用描画）
- `FOCUS_CAP = {well:'古井戸', shrine:'古い祠', lookout:'物見櫓', elder:'村長', herb:'薬草の女'}`
- `FOCUS_TXT = {...}` … +3 の取得時メッセージ（通常イベント文言と DRY 共有）
- `FOCUS_EVENT = {well:physDmg+2, shrine:hitAll+1, lookout:recon, elder:hitChief+2, herb:herbs+2}`
  … +3(と一部+2)の Z で付与する効果。**帳簿共有**（`S.visited` の key）で二重取得防止。
- `ROOM_SUBJ = {elder, herb}` … +2 の室内歩行シーン（room 背景 / npc 画像 / npc tile を切替）
- `ENEMY_IMG[kind][lv]` (kind: goblin/sentry/chief, lv: 1/2/3) … 敵の詳細度別画像
- `ENEMY_WEAK = {goblin:'まほう', sentry:'たたかう(物理)', chief:'まほう'}` … +3 で表示のみ

### メッセージ表示・取得済み分岐（過去バグの結晶）

- `msgShown() = S.focusInspected && S.msgLod===S.lod` … パネル表示は **LOD ごとに独立**
  （+2 と +3 の両方にメッセージがある対象で持ち越しを防ぐ）。
- `S.msgTaken` + `TAKEN_MSG='……もう十分に話を聞いた。'` … 取得済みで再 Z したら取得時文言を
  出さず取得済み文言に切替。`FOCUS_EVENT` 経路で全対象共通。
- `S.visited`（Set）が取得済み台帳。`S.prep`/`prepMax` が「準備」上限。

### +3 の精細表示（DOM img 経路）

内部 canvas は 256×224 と低解像度。ここに大画像を描くと潰れる。→ **+2/+3 の敵・focus 画像は
DOM `<img>` オーバーレイ**（`image-rendering:pixelated` / `object-fit:contain` / アスペクト保持）
で原寸表示する（`FOCUS_DOM`, `setFocusImg`）。テキスト/HPバー/メニューはその上に重ねる。

## 5. アセットパイプライン

- **背景**: 全生成画像はマゼンタ背景。**キー色は画像ごとに実測**（(220,39,144)〜(232,27,148) 等
  ばらつくので固定値にしない）。`key_bg(bg, tol=70, white=999)` + 囲まれマゼンタ tol45 +
  ピンクフリンジ除去。full-bleed 背景（tower_view / elder_room の内装）はキーせずクロップ。
- **命名**: source 原本は用途名（`ELDER_NPC.png` 等、敵は `enemy_{kind}_{lv}.png`）、
  生成物は `assets/focus/`（小文字）。
- **tools/**:
  - `build_*.py`（elder/herb/tower/enemy/focus/hero3x3）: 原本→透過生成物。
  - `embed_enemy.py`: 生成物を base64 で index.html に差し込み＋凍結行バイト不変 assert。
  - `conform.py`/`conform_hi.py`: base/HI アトラス生成（**base の完全再生成は不可**＝6ソース中
    4欠落。hero や shrine は `patch_base_*.py` で surgical 差し替え）。
  - `patch_base_hero.py`/`patch_base_shrine.py`: base アトラスの特定スプライトのみ差し替え。

## 6. Tier A 凍結テスト基盤（回帰ガード）

- **凍結タグ**: `tierA-hero-fix-v1`(bdfef4e, HIのみ) / `tierA-hero-fix-v2`(13dbea7, base+HI整合)。
  **タグは不変**。Tier A は常にタグ（=`13dbea7`）を測る＝ master に何を積んでも結果は不変。
- **テスト**: `test/tier-a-v2` ブランチに `tests/tier_a.py`（Pillow+numpy のみ、決定論的、
  ブラウザ不要）、`preregistration.md`(rc2)、`TIER_A_RUNBOOK.md`。対象タグには含めない。
- **検査内容**: (A) アトラス整合（矩形・非重複・34名カバレッジ・HI⊆base・inline↔disk 一致）、
  (B) hero 方向不変条件（rc2: down=顔あり&中央 / up=顔ゼロ / side=顔あり&右重心 ncx>0.57 /
  relative down≥5×up）。閾値 `T_FACE=0.08 T_NOFACE=0.01 T_CENTER=0.05 T_SIDE_RIGHT=0.57`。
- **合否**: self-test 37 / 本番 171、両方 exit 0。
- **実行**: Codex が worktree でタグを detached checkout → `python tests\tier_a.py --selftest` と
  `python tests\tier_a.py <target>`（RUNBOOK 参照）。ローカルでもオフライン実行可。
- **原則**: **hero と base/HI アトラスを触らなければ Tier A は無風**。詳細度コンテンツは
  すべてアトラス外なので、ランドマーク／敵の追加は Tier A に影響しない（毎回 37/171 継続）。

## 7. 現状の到達点

- **詳細度実装済み**: 井戸・祠・物見櫓・村長宅・薬草小屋（5ランドマーク）＋ モンスター（戦闘）。
- **コミット履歴（LOD 関連）**: 41ec580 井戸+3 → a53fb2a 祠 → 61b9dac 櫓 → 3c39589 村長 →
  1603245 薬師 → 5d770c3 モンスター。base hero 修正は 13dbea7（=v2 タグ）。
- **ブランチ**: `main`（正）, `test/tier-a-v2`（テスト隔離）。タグ v1/v2。
- **未着手**: Tier B（Playwright で実際に歩かせ／戦わせて挙動を assert。seed 注入と
  tick/moving フックの決定論化が前提）。

## 8. 新しい詳細度対象を1つ足す手順

1. **画像生成**（Nano Banana、マゼンタ背景、西洋中世ファンタジー16bit調で村と統一）。
   ランドマーク型なら +2用ちび/+2用内装/+3用全身、敵型なら +1簡素/+2中間/+3精細。
2. **実測**（キー色・bbox・詳細度の階段）。
3. **透過生成 + インライン化**（build/embed スクリプト、独立 Image、アトラスに入れない）。
4. **テーブルに1行**: FOCUS_IMG/CAP/TXT/EVENT（+3効果）、必要なら ROOM_SUBJ（+2室内歩行）や
   ENEMY_IMG/ENEMY_WEAK。
5. **入口判定**: near 関数 + `activeLandmark()`（または戦闘の対象選択）。
6. **専用シーンが要るなら**（櫓のような登攀、村長のような室内歩行）drawXxxScene を追加 or 一般化。
7. **コミット**（main へ。一時 UUID ファイルは除外）。**任意で Codex で Tier A**（37/171 継続確認）。

## 9. 既知の落とし穴（過去に踏んだもの）

- **和風に寄る**: NPC/内装プロンプトは "Western medieval-fantasy, NOT Japanese" を明記。
- **カードUI/文字が出る**: 敵の大写しで "boss card/framing" は禁止。"ABSOLUTELY NO text,
  ONLY the character" を明記。
- **詳細度の階段が潰れる**: +2 を「精細に」でなく "simple/low-detail/limited palette" と
  簡素側へ振る。palette 実測で +1<+2<+3 を確認。
- **hero 方向**: side は必ず右向き（左は反転生成）。3×3一括は右列が崩れるので方向別3帯生成→合成。
- **内部低解像度 canvas でぼやける**: +2/+3 の大画像は DOM img 経路で原寸表示（§4 末尾）。
- **メッセージ持ち越し / 取得済み再表示**: `msgShown()`(LOD分離) と `S.msgTaken`(取得済み分岐)。
- **ブランチ**: push 先は必ず `main`。過去に誤って origin/master を作った事故あり。
- **一時ファイル**: UUID 名のアップロード原本や preview_hi.png はコミットに含めない。

## 10. 凍結すべき不変（コミット時に毎回 assert）

- `SPR` / `SPR_HI` / `ATLAS.src` / `ATLAS_HI.src`（インライン base64 行）
- `sprAt` / `drawHeroImg` / blit 系
- `assets/hi/atlas_hi.png` / `assets/hi/manifest_hi.json`
- hero_* 9スプライトのピクセル（base/HI とも）
- 既存ランドマークの focus 画像（well_focus / shrine_focus / tower_* / elder_* / herb_*）の .src と png
- タグ `tierA-hero-fix-v1` / `tierA-hero-fix-v2`

これらが不変であれば Tier A v2 は 37/171 で pass し続ける（凍結ガードが機能している証跡）。
