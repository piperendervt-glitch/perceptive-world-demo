#!/usr/bin/env python3
# build_focus.py — 詳細度+3（ランドマーク クローズアップ鑑賞モード）専用画像を作る。
# assets/focus/<name>_focus_src.png（Nano Banana 出力・マゼンタ背景 1024x1024）を
# キー透過して assets/focus/<name>_focus.png を出力する。
# tools/build_focus_well.py の井戸専用処理を 2ランドマーク（well / shrine）に一般化したもの。
# ※ 既存の atlas.png / atlas_hi.png には一切触れない（+3 は独立アセット）。
import sys, numpy as np
from PIL import Image
from scipy import ndimage

# name -> (実測のマゼンタ背景, ドロップシャドウ等のピンク残りを追加除去するか)
SUBJECTS = {
    'well':   ((227, 24, 146), False),
    'shrine': ((222, 25, 138), True),
}

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
    """ドロップシャドウ／マゼンタ系のフリンジを除去（石・苔・縄・紙垂は影響なし）。"""
    rgb = a[:, :, :3].astype(int); r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    o = a.copy(); o[(o[:, :, 3] > 0) & (r > g + 40) & (b > g + 20), 3] = 0; return o

def bbox(a, at=24):
    ys, xs = np.where(a[:, :, 3] > at)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

def build(name):
    bg, pink = SUBJECTS[name]
    src = f'assets/focus/{name}_focus_src.png'
    dst = f'assets/focus/{name}_focus.png'
    a = np.array(Image.open(src).convert('RGBA'))
    a = key_bg(a, bg, tol=70, white=999)     # 白枠除去オフ・緑despillオフ
    d = np.sqrt(((a[:, :, :3].astype(int) - np.array(bg)) ** 2).sum(2))
    a[d < 45, 3] = 0                         # 囲まれマゼンタ（縄・腕木まわり等）
    if pink: a = drop_pink(a)
    x0, y0, x1, y1 = bbox(a)
    a = a[y0:y1, x0:x1]
    Image.fromarray(a.astype(np.uint8), 'RGBA').save(dst)
    print(f'{dst}: {a.shape[1]}x{a.shape[0]}  (bbox {x0},{y0}-{x1},{y1})')

if __name__ == '__main__':
    for n in (sys.argv[1:] or SUBJECTS):
        build(n)
