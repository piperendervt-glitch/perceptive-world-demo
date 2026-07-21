# TIER_A_RUNBOOK_V3

Tier A v3（アトラス整合 ＋ hero 方向 ＋ LOD 静的検証）を、凍結タグに対して実行するための手順書。
実行者（Codex / 人手）は、この手順を上から順に実行し、最後の「合格判定」を満たすことを確認する。

- 仕様: `preregistration-v3.md`（3.0-rc2）
- テスト実体: `tests/tier_a.py`（Pillow + numpy + 標準ライブラリ + 読み取り専用 Git のみ）
- 対象タグ: `tierA-lod-v3`
- 対象コミット: `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f`
- baseline タグ: `tierA-hero-fix-v2`
- baseline コミット: `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf`
- ハーネスブランチ: `test/tier-a-v3`（対象タグには含めない）

このテストは対象リポジトリ・タグ・アセットを**一切変更しない**（読み取りとテスト実行のみ）。
生成レポートはハーネス側にのみ出力され、対象 worktree には書き込まない。

v2 との違いは3点。**(1) baseline との突き合わせが必須**になり `--baseline-root` が要る。
**(2) checkpoint SHA が実 SHA に置換済み**なので、HEAD／annotated tag 照合が skip ではなく
必須検査になる。**(3) LOD（5ランドマーク＋モンスター）の静的検証が加わる**。

Tier B（Playwright による挙動検証）は本 RUNBOOK の対象外。`tests/tier_b/` ・
`playwright.config.mjs` ・preregistration §18 のテストフックは**未実装**であり、
この段階では実行しない。

---

## 0. 前提パス

| 記号 | パス | 状態 |
|---|---|---|
| MAIN | `C:\Users\pipe_render\dev\pw-work\perceptive-world-demo` | main（実装本体） |
| TARGET | `C:\Users\pipe_render\perceptive-world-demo-v3-target` | `tierA-lod-v3` を detached checkout（測定対象） |
| BASELINE | `C:\Users\pipe_render\perceptive-world-demo-v2-baseline` | `tierA-hero-fix-v2` を detached checkout（凍結領域の比較元） |
| HARNESS | `C:\Users\pipe_render\perceptive-world-demo-v3-tests` | branch `test/tier-a-v3`（`tests/tier_a.py` と `preregistration-v3.md` を保持） |

必要ツール: `git`、`python`（Pillow・numpy が import 可能なこと）。
ネットワークは不要。**すべてローカル worktree に対してオフラインで完結**する。

---

## 1. worktree の準備（既にあればスキップ）

```powershell
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree list
```

無いものだけ MAIN から作成する（preregistration §27.2 / §27.3）。

```powershell
cd C:\Users\pipe_render\dev\pw-work\perceptive-world-demo

# 測定対象（v3 タグを detached で）
git worktree add --detach C:\Users\pipe_render\perceptive-world-demo-v3-target tierA-lod-v3

# baseline（v2 タグを detached で）
git worktree add --detach C:\Users\pipe_render\perceptive-world-demo-v2-baseline tierA-hero-fix-v2

# ハーネス（branch test/tier-a-v3 は作成済み・push 済み）
git worktree add C:\Users\pipe_render\perceptive-world-demo-v3-tests test/tier-a-v3
```

既に `tierA-hero-fix-v2` を detached checkout した worktree がある場合
（例: v2 運用で作った `perceptive-world-demo-tierA-target`）、それを BASELINE として
そのまま `--baseline-root` に渡してよい。HEAD が `13dbea7…` であることだけ確認する。

---

## 2. 整合確認（読み取りのみ・実行前）

以下がすべて期待どおりでなければ、テスト本体を走らせる前に停止して報告する。

```powershell
# タグが対象コミットを指すこと
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo rev-parse "tierA-lod-v3^{commit}"
#  期待: 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo rev-parse "tierA-hero-fix-v2^{commit}"
#  期待: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf

# TARGET / BASELINE の HEAD と clean 状態
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target rev-parse HEAD
#  期待: 5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target status --porcelain
#  期待: 出力なし
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline rev-parse HEAD
#  期待: 13dbea7deec6e5994501ffc5e70b47e9d0e24dcf
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline status --porcelain
#  期待: 出力なし

# ハーネスのブランチ
git -C C:\Users\pipe_render\perceptive-world-demo-v3-tests branch --show-current
#  期待: test/tier-a-v3

# テストファイルが対象タグに混入していないこと
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo ls-tree -r tierA-lod-v3 --name-only | findstr /R "tier_a preregistration-v3 TIER_A_RUNBOOK_V3 tests/ playwright package"
#  期待: 出力なし（findstr の exit code は 1 = 一致ゼロ。これは正常）
```

補足: `findstr` は一致ゼロのとき exit 1 を返す。ここでの exit 1 は「禁止ファイル未混入＝正常」の意味で、
テストの失敗ではない。checker 側も `SETUP.TARGET.HARNESS_ABSENT` で同じことを検査する。

---

## 3. 実行

HARNESS ディレクトリから実行する（レポートは HARNESS 側に生成される）。

```powershell
cd C:\Users\pipe_render\perceptive-world-demo-v3-tests

Remove-Item .\tier_a_v3_selftest_report.json -ErrorAction SilentlyContinue
python tests\tier_a.py --selftest
Write-Output "TIER_A_SELFTEST_EXIT=$LASTEXITCODE"

Remove-Item .\tier_a_v3_report.json -ErrorAction SilentlyContinue
python tests\tier_a.py `
  --baseline-root C:\Users\pipe_render\perceptive-world-demo-v2-baseline `
  C:\Users\pipe_render\perceptive-world-demo-v3-target
Write-Output "TIER_A_EXIT=$LASTEXITCODE"
```

- `--selftest`: 対象に依存しない in-memory の負テスト＋正の対照を実行し、
  `tier_a_v3_selftest_report.json` を書き出す。
- 本番検証: **`--baseline-root` は必須**（省略すると `SetupError` で exit 2）。
  第1引数が TARGET。`tier_a_v3_report.json` を書き出す。

非0で終了してもレポートは保存される。失敗 check はそのまま報告する。

---

## 4. 実行後確認（読み取りのみ）

```powershell
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v3-target rev-parse HEAD
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline status --porcelain
git -C C:\Users\pipe_render\perceptive-world-demo-v2-baseline rev-parse HEAD
```

実行前後で clean と HEAD が一致しなければならない（checker も
`SETUP.*.CLEAN_AFTER` / `SETUP.TARGET.HEAD_UNCHANGED` で自動検査する）。

生成レポートは HARNESS 側にのみ存在し、`test/tier-a-v3` の `.gitignore`（`tier_a_v3_*.json`）
により追跡対象外。TARGET・BASELINE・main・タグ v1/v2/v3 は変更されない。

---

## 5. 合格判定

以下がすべて満たされたとき、Tier A v3 は合格。

| 項目 | 期待値 |
|---|---|
| `tierA-lod-v3^{commit}` | `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f` |
| `tierA-hero-fix-v2^{commit}` | `13dbea7deec6e5994501ffc5e70b47e9d0e24dcf` |
| TARGET / BASELINE HEAD | 上記に一致 |
| TARGET / BASELINE status（実行前 / 実行後） | clean（出力なし） |
| 禁止ファイル混入 | なし |
| `tier_a.py --selftest` | exit 0 / `overall_status: pass` / **100 passed / 0 failed / 0 skipped** |
| `tier_a.py --baseline-root <BASELINE> <TARGET>` | exit 0 / `overall_status: pass` / **failed 0 / skipped 0** |
| `tier_a_v3_report.json` の `preregistration.checkpoint_commit` | `5d770c3c8cd1524acd32baeea9cd0c5c5bf8381f` |
| 同 `checkpoint_is_placeholder` | `false` |
| `SETUP.TARGET.CHECKPOINT_HEAD` / `SETUP.TARGET.CHECKPOINT_TAG` | `pass`（**`skip` は不可**） |
| `SETUP.BASELINE.CHECKPOINT_HEAD` / `SETUP.BASELINE.CHECKPOINT_TAG` | `pass` |

checkpoint SHA が実 SHA に置換済みのため、v2 で `skip` だった HEAD／annotated tag 照合は
v3 では**必須検査**である。これらが `skip` と報告された場合は checker が
未置換版（`<V3_CHECKPOINT>`）である可能性が高いので、`EXPECTED_COMMIT` を確認する。

いずれかが非0 / fail の場合は、**失敗した check id と `measured` 値をそのまま報告する**
（閾値の再解釈や手動での合格判定はしない）。

---

## 6. Exit code の意味（preregistration §29）

```text
0 : 全必須チェック合格＋レポート書き込み成功
1 : preregister された不変条件のいずれかが不合格
2 : setup / checkpoint 整合 / 抽出 / 依存 / 内部実行 / レポート書き込みの失敗
```

self-test も同じ体系（0 = 全ての正の対照が合格し全ての負フィクスチャが棄却された）。
JSON レポートの `exit_code` / `overall_status` はプロセスの exit code と一致する。

---

## 7. 禁止事項（実行者が行ってはならないこと）

- 対象タグ・対象コミットの更新、`git pull` / `fetch` による TARGET の最新化
  （凍結タグ `5d770c3` を測るのが目的。更新は測定対象を変えてしまう）。
- `test/tier-a-v3` を main へマージ（テストが対象タグに混入すると preregistration §2.3 違反）。
- 生成レポート（`tier_a_v3_report.json` / `tier_a_v3_selftest_report.json`）のコミット。
- 閾値・定数（`T_FACE=0.08 / T_NOFACE=0.01 / T_CENTER=0.05 / T_SIDE_RIGHT=0.57 /
  T_DOWN_UP_RATIO=5.0`）、C/D 検査項目、negative self-test の ID・定数、hero 方向述語の書き換え。
- 敵基礎値・弱点文字列・イベント効果・キー集合など preregistration §29 の凍結定数の変更。
- 不合格チェックを「入力が不都合だから」という理由で `skip` に変換すること。

---

## 8. トラブルシューティング

**`SETUP.EXTRACTION_OR_DEPENDENCY` が fail（JavaScript static parse error）**
rc2 checker の JS オブジェクトリテラル解析は、値が**文字列リテラルのときのみ**を想定している。
`index.html` の `FOCUS_TXT` は `shrine:SHRINE_MSG.body+'<span…>'+SHRINE_MSG.gain+'</span>'` の
ように**連結式**を値に持つため、ここで停止する（`a53fb2a`〜現在まで存在する既存構文で、
LOD 実装で新たに入ったものではない）。
これは checker 側の制約であり、**実装側を書き換えて回避してはならない**。
発生したら check id と `message` をそのまま報告し、preregistration の改訂（パーサが
式値を許容する rc3）で解決する。

**`fatal: detected dubious ownership` / exit 128（所有者保護）**

```powershell
git config --global --add safe.directory C:/Users/pipe_render/dev/pw-work/perceptive-world-demo
git config --global --add safe.directory C:/Users/pipe_render/perceptive-world-demo-v3-target
git config --global --add safe.directory C:/Users/pipe_render/perceptive-world-demo-v2-baseline
git config --global --add safe.directory C:/Users/pipe_render/perceptive-world-demo-v3-tests
```

**`ModuleNotFoundError: No module named 'PIL'` / `numpy`**
`python -m pip install pillow numpy` を実行してから再試行する
（Tier A の許可依存は Pillow・numpy・標準ライブラリ・読み取り専用 Git のみ）。

**`--baseline-root is required for Tier A v3 verification`（exit 2）**
v3 は baseline 突き合わせが必須。`--baseline-root` に v2 タグの worktree を渡す。

**`git worktree add` が「already exists」で失敗する**
既に worktree があるか、対象ブランチが使用中。手順1の `worktree list` で状態を確認する。

**GitHub への clone が名前解決エラーになる**
Tier A は clone 不要。既存ローカル worktree に対してオフラインで実行する（本手順のとおり）。

---

## 9. 後片付け（この検証を一区切りにする場合のみ）

```powershell
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree remove C:\Users\pipe_render\perceptive-world-demo-v3-target
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree remove C:\Users\pipe_render\perceptive-world-demo-v2-baseline
git -C C:\Users\pipe_render\dev\pw-work\perceptive-world-demo worktree remove C:\Users\pipe_render\perceptive-world-demo-v3-tests
```

ブランチ `test/tier-a-v3` とタグ v1/v2/v3 は残る。再実行を続ける場合は撤去しないこと。

---

## 付記

- テスト仕様は `preregistration-v3.md`（3.0-rc2）が正。本 RUNBOOK は実行手順のみを扱い、
  合否条件・閾値は preregistration を上書きしない。
- v2 の資産（タグ `tierA-hero-fix-v2`、ブランチ `test/tier-a-v2`、`preregistration.md`、
  既存レポート）は変更しない。v3 は別ブランチ・別レポート名で並走する。
- Codex への報告様式は preregistration §28 に従う。
