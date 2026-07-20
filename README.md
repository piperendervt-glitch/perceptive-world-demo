# Perceptive World — Visual Demo

「ゴブリン討伐」シナリオの **見た目（グラフィックス）の方向性を認識合わせするための2Dデモ**です。
ファミコン／スーファミ風のドット絵で、村・室内・洞窟の探索と、2D6ベースのコマンド戦闘を1画面で体験できます。

> **派生元 (provenance)**: 本リポジトリは決定論的TRPGエンジン
> [`perceptive-world`](https://github.com/piperendervt-glitch/perceptive-world) の
> `feature/chatgpt-implementation` ブランチ（ChatGPT設計・Codex実装）から、
> **見た目デモ用に独立させた新規リポジトリ**です。エンジン本体（`trpg_core`）は含みません。
> ゲームデータ・ビジュアル基準（`design/` 配下）は派生元の該当ファイルを引き継いでいます。

## クイックスタート

`index.html` をブラウザで開くだけで動きます（ビルド不要・依存なし・オフライン可）。

- 移動: 矢印キー / 決定・調べる: `Z` / キャンセル: `X`
- スマホ: 画面の十字キー＋A/Bボタン

## リポジトリ構成

```
index.html                     … デモ本体（単一HTML。CSS/JS/Base64アトラス同梱）
tools/conform.py               … 素材加工スクリプト（AI生成シート → 透過・切出し・アトラス化）
assets/
  source/                      … AI生成の元シート（Nano Banana 出力の PNG を置く）
  hi/                          … 高精細（詳細度+2用）に加工したスプライト／アトラスの出力先
  reference/two_d/goblin/      … 派生元エンジンの正準LODアセット（lod0〜3）※視覚参照
design/
  visual_bible.yaml            … キャラ・画風の視覚記述子（画像生成の一貫性基準）※派生元より
  image_prompts.yaml           … 画像生成プロンプト集 ※派生元より
  scenario-goblin.yaml         … 「ゴブリン討伐」ゲームデータ ※派生元より
CLAUDE.md                      … 開発の引き継ぎ・作業方針（Claude Code 用）
```

## 現在の最優先タスク

ズームの **「詳細度+2」表示を、高精細画像（Nano Banana 出力）に置き換える**。
詳細は `CLAUDE.md` の「## 0. 進行中の作業」を参照。

## ライセンス / 権利

素材・コードの取り扱いは派生元リポジトリの方針に従う。AI生成画像の権利表記が必要な場合は別途追記。
