#!/usr/bin/env python3
# build_tower.py — 物見櫓（+1/+2/+3 登攀シーケンス）専用の独立画像を作る。3系統:
#   +1  assets/source/tower_full.png (マゼンタ背景 1024x1024)
#         → 透過 → assets/focus/tower_full.png … 櫓を下から見上げる1本もの（分割しない）
#   +2  assets/source/tower_top.png  (マゼンタ背景 1024x1024)
#         → 透過 → assets/focus/tower_top.png  … 見張り台（屋根＋手すり＋板デッキ）
#   +3  assets/focus/tower_view.png                … 全面風景（キー不要・そのまま／再生成しない）
# ※ atlas.png / atlas_hi.png / well_focus / shrine_focus には一切触れない（tower は独立枠）。
import numpy as np
from PIL import Image
from scipy import ndimage

FULL_SRC = 'assets/source/tower_full.png'  # +1 用（全体を使う）
TOP_SRC  = 'assets/source/tower_top.png'   # +2 用（見張り台の正面ビュー）
OUT = 'assets/focus'
FULL_BG = (209, 26, 121)   # tower_full の実測マゼンタ背景
TOP_BG  = (227, 16, 166)   # tower_top の実測マゼンタ背景

def remove_border_region(a, mask):
    lbl, n = ndimage.label(mask)
    border = set(lbl[0, :]).union(lbl[-1, :]).union(lbl[:, 0]).union(lbl[:, -1])
    border.discard(0)
    rm = np.isin(lbl, list(border))
    out = a.copy(); out[rm, 3] = 0; return out

def key_bg(a, bg, tol=60, white=196):
    rgb = a[:, :, :3].astype(int)
    d = np.sqrt(((rgb - np.array(bg)) ** 2).sum(2))
    frame = rgb.min(2) > white
    return remove_border_region(a, (d < tol) | frame)

def drop_pink(a):
    """マゼンタ系のフリンジを除去（木・石・苔・空は影響なし）"""
    rgb = a[:, :, :3].astype(int); r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    o = a.copy(); o[(o[:, :, 3] > 0) & (r > g + 40) & (b > g + 20), 3] = 0; return o

def bbox(a, at=24):
    ys, xs = np.where(a[:, :, 3] > at)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

def cutout(src, bg):
    """マゼンタ背景を抜いて bbox で詰める（囲まれマゼンタ＝手すりの隙間や脚の間も抜く）"""
    a = np.array(Image.open(src).convert('RGBA'))
    a = key_bg(a, bg, tol=70, white=999)          # 白枠除去オフ・despill不要
    d = np.sqrt(((a[:, :, :3].astype(int) - np.array(bg)) ** 2).sum(2))
    a[d < 45, 3] = 0                              # 格子の内側など囲まれマゼンタ
    a = drop_pink(a)
    x0, y0, x1, y1 = bbox(a)
    return a[y0:y1, x0:x1]

def main():
    for name, src, bg in (('tower_full', FULL_SRC, FULL_BG), ('tower_top', TOP_SRC, TOP_BG)):
        a = cutout(src, bg)
        Image.fromarray(a.astype(np.uint8), 'RGBA').save(f'{OUT}/{name}.png')
        print(f'{OUT}/{name}.png: {a.shape[1]}x{a.shape[0]}')
    print(f'{OUT}/tower_view.png: left as-is (+3 background, not regenerated)')

if __name__ == '__main__':
    main()
