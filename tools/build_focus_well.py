#!/usr/bin/env python3
# build_focus_well.py — 詳細度+3（井戸クローズアップ鑑賞モード）専用の井戸画像を作る。
# assets/focus/well_focus_src.png（Nano Banana 出力・マゼンタ背景 1024x1024）を
# キー透過して assets/focus/well_focus.png を出力する。
# ※ 既存の atlas.png / atlas_hi.png には一切触れない（+3 は独立アセット）。
import os, numpy as np
from PIL import Image
from scipy import ndimage

SRC = 'assets/focus/well_focus_src.png'
DST = 'assets/focus/well_focus.png'
BG  = (227, 24, 146)          # 実測のマゼンタ背景

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

def bbox(a, at=24):
    ys, xs = np.where(a[:, :, 3] > at)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

def main():
    a = np.array(Image.open(SRC).convert('RGBA'))
    # 白枠除去オフ・緑despillオフ（背景が緑ではないため despill 不要）
    a = key_bg(a, BG, tol=70, white=999)
    # 腕木/縄まわりの「囲まれたマゼンタ」は縁と繋がらないので色キーで別途除去
    d = np.sqrt(((a[:, :, :3].astype(int) - np.array(BG)) ** 2).sum(2))
    a[d < 45, 3] = 0
    x0, y0, x1, y1 = bbox(a)
    a = a[y0:y1, x0:x1]
    Image.fromarray(a.astype(np.uint8), 'RGBA').save(DST)
    print(f'{DST}: {a.shape[1]}x{a.shape[0]}  (bbox {x0},{y0}-{x1},{y1})')

if __name__ == '__main__':
    main()
