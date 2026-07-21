#!/usr/bin/env python3
# embed_enemy.py — build_enemy.py が作った 9 枚を index.html にインライン埋め込みする。
# 敵画像はアトラス外の独立アセットなので、ランドマークの +3 画像と同じく
# `<VAR>.src="data:image/png;base64,..."` の 1 行 1 枚で持たせる。
#
# 差し込み先は index.html 内のマーカー行の間だけ:
#   // <<< enemy-detail art (embed_enemy.py)
#   // >>> enemy-detail art
# 何度実行しても同じ結果になる（マーカー間を毎回作り直す）。
#
# Tier A 無風の担保: SPR / ATLAS.src / SPR_HI / ATLAS_HI.src と、
# ランドマークの focus 画像行がバイト単位で不変であることを実行前後で検証する。
import base64, sys

HTML = 'index.html'
KINDS = ('goblin', 'sentry', 'chief')
LEVELS = (1, 2, 3)
BEGIN = '// <<< enemy-detail art (embed_enemy.py)'
END = '// >>> enemy-detail art'
# 触ってはいけない行（行頭一致）。実行前後で完全一致を確認する。
FROZEN = ('const SPR=', 'ATLAS.src=', 'const SPR_HI=', 'ATLAS_HI.src=',
          'WELL_FOCUS.src=', 'SHRINE_FOCUS.src=', 'TOWER_TOP.src=', 'TOWER_FULL.src=',
          'TOWER_VIEW.src=', 'ELDER_ROOM.src=', 'ELDER_NPC.src=', 'ELDER_FOCUS.src=',
          'HERB_ROOM.src=', 'HERB_NPC.src=', 'HERB_FOCUS.src=')


def frozen_lines(lines):
    return [l for l in lines if l.startswith(FROZEN)]


def main():
    html = open(HTML, 'r', encoding='utf-8', newline='').read()
    lines = html.split('\n')
    before = frozen_lines(lines)
    assert len(before) == len(FROZEN), f'frozen lines: expected {len(FROZEN)}, found {len(before)}'

    try:
        b = lines.index(BEGIN); e = lines.index(END)
    except ValueError:
        sys.exit('marker not found in index.html — 先に宣言ブロックを入れること')
    assert b < e, 'markers out of order'

    art, total = [], 0
    for k in KINDS:
        for lv in LEVELS:
            p = f'assets/focus/enemy_{k}_{lv}.png'
            raw = open(p, 'rb').read(); total += len(raw)
            art.append(f'ENEMY_IMG.{k}[{lv}].src="data:image/png;base64,'
                       + base64.b64encode(raw).decode('ascii') + '";')
            print(f'  {p}: {len(raw):,} bytes')

    out = lines[:b + 1] + art + lines[e:]
    after = frozen_lines(out)
    assert after == before, 'FROZEN LINES CHANGED'   # アトラス・ランドマークは絶対に触らない

    open(HTML, 'w', encoding='utf-8', newline='').write('\n'.join(out))
    print(f'index.html: embedded {len(art)} enemy images ({total:,} bytes raw); '
          f'frozen lines verified byte-identical ({len(before)} lines)')


if __name__ == '__main__':
    main()
