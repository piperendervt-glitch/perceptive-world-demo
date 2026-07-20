# TIER_A_RUNBOOK

Tier A（アトラス整合＋hero 方向の静的回帰ガード）を、凍結タグに対して実行するための手順書。
実行者（Codex / 人手）は、この手順を上から順に実行し、最後の「合格判定」を満たすことを確認する。

- 仕様: `preregistration.md`（rc2）
- テスト実体: `tests/tier_a.py`（Pillow + numpy + 標準ライブラリ + 読み取り専用 Git のみ）
- 対象タグ: `tierA-hero-fix-v2`
- 対象コミット: `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf`

このテストは対象リポジトリ・タグ・アセットを**一切変更しない**（読み取りとテスト実行のみ）。
生成レポートはハーネス側にのみ出力され、対象 worktree には書き込まない。

---

## 0. 前提パス

| 記号 | パス | 状態 |
|---|---|---|
| MAIN | `C:\Users\pipe_render\dev\pw-work\perceptive-world-demo` | master（実装ベース `13dbea7`） |
| TARGET | `C:\Users\pipe_render\perceptive-world-demo-tierA-target` | `tierA-hero-fix-v2` を detached checkout（読み取り専用の測定対象） |
| HARNESS | `C:\Users\pipe_render\perceptive-world-demo-tierA-harness` | branch `test/tier-a-v2`（`tests/tier_a.py` と `preregistration.md` を保持） |

必要ツール: `git`、`python`（Pillow・numpy が import 可能なこと）。
ネットワークは不要。**すべてローカル worktree に対してオフラインで完結**する。

---

## 1. worktree の準備（既にあればスキップ）

まず既存の worktree を確認する。

```powershell
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree list
```

期待される3行（順不同）:

```text
.../perceptive-world-demo                    13dbea7 [master]
.../perceptive-world-demo-tierA-harness      <sha>   [test/tier-a-v2]
.../perceptive-world-demo-tierA-target       13dbea7 (detached HEAD)
```

TARGET / HARNESS が無い場合のみ、MAIN から作成する。

```powershell
cd C:\Users\pipe_render\dev\pw-work\perceptive-world-demo
git fetch origin --tags

# 測定対象（タグを detached で。実装＋アセットのみ）
git worktree add --detach C:\Users\pipe_render\perceptive-world-demo-tierA-target tierA-hero-fix-v2

# ハーネス（branch test/tier-a-v2 は作成済み・push 済みなので、既存ブランチから展開）
git worktree add C:\Users\pipe_render\perceptive-world-demo-tierA-harness test/tier-a-v2
# ※ もし test/tier-a-v2 がまだ存在しない初回のみ:
#   git worktree add -b test/tier-a-v2 C:\Users\pipe_render\perceptive-world-demo-tierA-harness tierA-hero-fix-v2
```

---

## 2. 整合確認（読み取りのみ・実行前）

以下がすべて期待どおりでなければ、テスト本体を走らせる前に停止して報告する。

```powershell
# タグが対象コミットを指すこと
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo rev-parse "tierA-hero-fix-v2^{commit}"
#  期待: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

# TARGET の HEAD が同じコミットであること
git -C C:\Users\pipe_render\perceptive-world-demo-tierA-target rev-parse HEAD
#  期待: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

# TARGET が clean（未コミット変更なし）であること
git -C C:\Users\pipe_render\perceptive-world-demo-tierA-target status --porcelain
#  期待: 出力なし

# テストファイルが対象タグに混入していないこと
git -C C:\Users\pipe_render\perceptive-world-demo-tierA-target ls-files | findstr /R "tier_a.py preregistration.md TIER_A_RUNBOOK.md"
#  期待: 出力なし（findstr の exit code は 1 = 一致ゼロ。これは正常）
```

補足: `findstr` は一致ゼロのとき exit 1 を返す。ここでの exit 1 は「禁止ファイル未混入＝正常」の意味で、テストの失敗ではない。

---

## 3. 実行

HARNESS ディレクトリから実行する（レポートは HARNESS 側に生成される）。

```powershell
cd C:\Users\pipe_render\perceptive-world-demo-tierA-harness

python tests\tier_a.py --selftest
python tests\tier_a.py C:\Users\pipe_render\perceptive-world-demo-tierA-target
```

- 第1コマンド（`--selftest`）: 対象に依存しない in-memory の負テスト＋正の対照を実行し、
  `tier_a_selftest_report.json` を書き出す。
- 第2コマンド: TARGET を引数に、実タグの committed blob に対して本番検証を実行し、
  `tier_a_report.json` を書き出す。

---

## 4. 実行後確認（読み取りのみ）

```powershell
# TARGET が実行後も clean（テストが対象を汚していない）
git -C C:\Users\pipe_render\perceptive-world-demo-tierA-target status --porcelain
#  期待: 出力なし
```

生成レポート（`tier_a_report.json` / `tier_a_selftest_report.json`）は HARNESS 側にのみ存在し、
`test/tier-a-v2` の `.gitignore` により追跡対象外。TARGET・master・タグ v1/v2 は変更されない。

---

## 5. 合格判定

以下がすべて満たされたとき、Tier A v2 は合格。

| 項目 | 期待値 |
|---|---|
| `tierA-hero-fix-v2^{commit}` | `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf` |
| TARGET HEAD | 同上 |
| TARGET status（実行前 / 実行後） | clean（出力なし） |
| 禁止ファイル混入 | なし |
| `tier_a.py --selftest` | exit 0 / `overall_status: pass` / **37 passed / 0 failed / 0 skipped** |
| `tier_a.py <TARGET>` | exit 0 / `overall_status: pass` / **171 passed / 0 failed / 0 skipped** |
| `tier_a_report.json` の `preregistration.checkpoint_commit` | `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf` |

いずれかが非0 / fail の場合は、**失敗した check id と `measured` 値をそのまま報告する**
（閾値の再解釈や手動での合格判定はしない）。

---

## 6. Exit code の意味（preregistration §15）

本番検証:

```text
0 : 全必須チェック合格＋レポート書き込み成功
1 : preregister された不変条件のいずれかが不合格
2 : setup / checkpoint 整合 / 抽出 / 依存 / 内部実行 / レポート書き込みの失敗
```

self-test:

```text
0 : 全ての正の対照が合格し、全ての負フィクスチャが意図した checker に棄却された
1 : self-test の期待のいずれかが不成立
2 : self-test の setup / 内部実行 / レポート書き込みの失敗
```

JSON レポートの `exit_code` / `overall_status` は、プロセスの exit code と一致する。

---

## 7. 禁止事項（実行者が行ってはならないこと）

- 対象タグ・対象コミットの更新、`git pull` / `fetch` による TARGET の最新化
  （凍結タグ `13dbea7` を測るのが目的。更新は測定対象を変えてしまう）。
- `test/tier-a-v2` を master / main へマージ（テストが対象タグに混入すると §2.2 違反）。
- 生成レポート（`tier_a_report.json` / `tier_a_selftest_report.json`）のコミット。
- 閾値・定数（`T_FACE=0.08 / T_NOFACE=0.01 / T_CENTER=0.05 / T_SIDE_RIGHT=0.57 / T_DOWN_UP_RATIO=5.0`）
  や判定則の書き換え。
- 不合格チェックを「入力が不都合だから」という理由で `skip` に変換すること。

---

## 8. トラブルシューティング

**`fatal: detected dubious ownership` / exit 128（所有者保護）**
サンドボックスユーザー等でリポジトリ所有者と実行ユーザーが異なると Git が停止する。
リポジトリ所有者側の権限で再実行するか、恒久回避する場合:

```powershell
git config --global --add safe.directory C:/Users/pipe_render/dev/pw-work/perceptive-world-demo
git config --global --add safe.directory C:/Users/pipe_render/perceptive-world-demo-tierA-target
git config --global --add safe.directory C:/Users/pipe_render/perceptive-world-demo-tierA-harness
```

**`ModuleNotFoundError: No module named 'PIL'` / `numpy`**
依存不足。`python -m pip install pillow numpy` を実行してから再試行する
（Tier A の許可依存は Pillow・numpy・標準ライブラリ・読み取り専用 Git のみ）。

**GitHub への clone が名前解決エラーになる**
Tier A は clone 不要。既存ローカル worktree に対してオフラインで実行する（本手順のとおり）。

**`git worktree add` が「already exists」で失敗する**
既に worktree があるか、対象ブランチが使用中。手順1の `worktree list` で状態を確認する。

---

## 9. 後片付け（この検証を一区切りにする場合のみ）

worktree を撤去する（ブランチ `test/tier-a-v2` とタグ v1/v2 は残る）。

```powershell
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree remove C:\Users\pipe_render\perceptive-world-demo-tierA-target
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree remove C:\Users\pipe_render\perceptive-world-demo-tierA-harness
```

Codex による再実行を続ける場合は撤去しないこと（毎回同じ worktree を再利用する）。

---

## 付記

- テスト仕様は `preregistration.md`（rc2）が正。本 RUNBOOK は実行手順のみを扱い、
  合否条件・閾値は preregistration を上書きしない。
- `test/tier-a-v2` に配置されている `preregistration.md` の `test_branch` フィールドは
  表記上 `test/tier-a-v1` のままだが、これは運用メタ表記であり合否条件には影響しない
  （実ブランチは `test/tier-a-v2`）。次回の preregistration 改訂時に合わせるとよい。
