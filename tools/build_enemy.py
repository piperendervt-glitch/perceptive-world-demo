#!/usr/bin/env python3
# build_enemy.py — 戦闘シーンの「モンスター詳細度 +1/+2/+3」用の敵画像を作る。
# assets/source/enemy_<kind>_<lv>.png（Nano Banana 出力・マゼンタ背景 1024x1024）を
# キー透過して assets/focus/enemy_<kind>_<lv>.png を出力する。
# build_focus.py と同じキー抜き手順だが、背景のマゼンタは敵ごと・詳細度ごとに違う
# （例 goblin+1≈(220,39,144) / sentry+3≈(227,30,141)）ため、固定色は使わず
# 各ファイルの外周から実測する。
# ※ atlas.png / atlas_hi.png には一切触れない（敵画像はアトラス外の独立アセット）。
import sys, numpy as np
from PIL import Image
from scipy import ndimage

KINDS = ('goblin', 'sentry', 'chief')
LEVELS = (1, 2, 3)
# 詳細度ごとの出力上限（長辺 px）。+3 は「原寸精細」なので縮小しない。
# +1 は表に載せるだけで描画には使わず、+2 は 256x224 のキャンバスに contain 描画する。
MAXSIDE = {1: 128, 2: 320, 3: None}


def measure_bg(a):
    """外周 1px リングの最頻色 = そのファイルのマゼンタ背景色（実測）。"""
    ring = np.concatenate([a[0, :, :3], a[-1, :, :3], a[:, 0, :3], a[:, -1, :3]])
    cols, cnt = np.unique(ring.reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in cols[cnt.argmax()])


def remove_border_region(a, mask):
    """画像の縁と繋がっている領域だけを透過する（内部の同色は残す）。"""
    lbl, n = ndimage.label(mask)
    border = set(lbl[0, :]).union(lbl[-1, :]).union(lbl[:, 0]).union(lbl[:, -1])
    border.discard(0)
    rm = np.isin(lbl, list(border))
    out = a.copy(); out[rm, 3] = 0; return out


def key_bg(a, bg, tol=60, white=196):
    rgb = a[:, :, :3].astype(int)
    d = np.sqrt(((rgb - np.array(bg)) ** 2).sum(2))
    frame = rgb.min(2) > white               # 白セル枠（white=999 で無効化）
    return remove_border_region(a, (d < tol) | frame)


def drop_pink(a):
    """マゼンタ系のフリンジを除去（緑の肌・茶の腰布・赤い目や傷は条件を満たさず残る）。"""
    rgb = a[:, :, :3].astype(int); r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    o = a.copy(); o[(o[:, :, 3] > 0) & (r > g + 40) & (b > g + 20), 3] = 0; return o


def shrink(im, ms):
    """アルファ乗算してから縮小する。透明画素に残ったマゼンタが縁ににじむのを防ぐ。"""
    a = np.array(im).astype(np.float64)
    al = a[:, :, 3:4] / 255.0
    a[:, :, :3] *= al                                   # premultiply
    s = ms / max(im.size)
    w, h = max(1, round(im.width * s)), max(1, round(im.height * s))
    r = np.array(Image.fromarray(a.astype(np.uint8), 'RGBA').resize((w, h), Image.LANCZOS)).astype(np.float64)
    ra = np.clip(r[:, :, 3:4], 0, 255) / 255.0
    r[:, :, :3] = np.where(ra > 0, r[:, :, :3] / np.maximum(ra, 1e-6), 0)   # unpremultiply
    return Image.fromarray(np.clip(r, 0, 255).astype(np.uint8), 'RGBA')


def bbox(a, at=24):
    ys, xs = np.where(a[:, :, 3] > at)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def build(kind, lv):
    src = f'assets/source/enemy_{kind}_{lv}.png'
    dst = f'assets/focus/enemy_{kind}_{lv}.png'
    a = np.array(Image.open(src).convert('RGBA'))
    bg = measure_bg(a)                       # ← 固定色にせず 1 枚ずつ実測
    a = key_bg(a, bg, tol=70, white=999)     # 白枠除去オフ
    d = np.sqrt(((a[:, :, :3].astype(int) - np.array(bg)) ** 2).sum(2))
    a[d < 45, 3] = 0                         # 囲まれマゼンタ（腕と胴の間・武器の穴など）
    a = drop_pink(a)
    x0, y0, x1, y1 = bbox(a)
    a = a[y0:y1, x0:x1]
    im = Image.fromarray(a.astype(np.uint8), 'RGBA')
    ms = MAXSIDE[lv]
    if ms and max(im.size) > ms:
        im = shrink(im, ms)
    im.save(dst, optimize=True)
    print(f'{dst}: {im.width}x{im.height}  bg={bg}  (bbox {x0},{y0}-{x1},{y1})')


if __name__ == '__main__':
    args = sys.argv[1:]
    kinds = [k for k in args if k in KINDS] or list(KINDS)
    for k in kinds:
        for lv in LEVELS:
            build(k, lv)
