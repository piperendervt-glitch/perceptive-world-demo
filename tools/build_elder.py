#!/usr/bin/env python3
# build_elder.py — 村長宅の詳細度 +2/+3 用の独立画像を作る（アトラス外）。
#   assets/source/ELDER_NPC.png   (マゼンタ背景) → 透過 → assets/focus/elder_npc.png   … +2 の村長ちび
#   assets/source/ELDER_FOCUS.png (マゼンタ背景) → 透過 → assets/focus/elder_focus.png … +3 の村長全身
#   assets/source/ELDER_ROOM.png  (白枠つき内装) → 白枠クロップのみ（キーしない）
#                                                → assets/focus/elder_room.png  … +2 の背景（下辺中央が扉）
# ※ atlas.png / atlas_hi.png / well_focus / shrine_focus / tower_* には一切触れない。
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = 'assets/source'; OUT = 'assets/focus'
NPC_BG   = (194, 18, 138)   # ELDER_NPC の実測マゼンタ背景
FOCUS_BG = (221, 45, 150)   # ELDER_FOCUS の実測マゼンタ背景
ROOM_WHITE = (225, 235, 215)    # ELDER_ROOM の白枠の下限しきい値（これより明るい＝枠）
                                # 部屋 bbox は実測 (66,18)-(958,991) だが、素材差し替えに強いよう自動検出する

def remove_border_region(a, mask):
    lbl, n = ndimage.label(mask)
    border = set(lbl[0, :]).union(lbl[-1, :]).union(lbl[:, 0]).union(lbl[:, -1])
    border.discard(0)
    out = a.copy(); out[np.isin(lbl, list(border)), 3] = 0; return out

def key_bg(a, bg, tol=60, white=196):
    rgb = a[:, :, :3].astype(int)
    d = np.sqrt(((rgb - np.array(bg)) ** 2).sum(2))
    return remove_border_region(a, (d < tol) | (rgb.min(2) > white))

def drop_pink(a):
    """マゼンタ系のフリンジ／影を除去（青ローブ・白髭・木の杖は影響なし）"""
    rgb = a[:, :, :3].astype(int); r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    o = a.copy(); o[(o[:, :, 3] > 0) & (r > g + 40) & (b > g + 20), 3] = 0; return o

def bbox(a, at=24):
    ys, xs = np.where(a[:, :, 3] > at)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1

def cutout(name, bg):
    a = np.array(Image.open(f'{SRC}/{name}.png').convert('RGBA'))
    a = key_bg(a, bg, tol=70, white=999)          # 白枠除去オフ・despill不要
    d = np.sqrt(((a[:, :, :3].astype(int) - np.array(bg)) ** 2).sum(2))
    a[d < 45, 3] = 0                              # 腕と体の隙間など囲まれマゼンタ
    a = drop_pink(a)
    x0, y0, x1, y1 = bbox(a)
    return a[y0:y1, x0:x1]

def main():
    for src, dst, bg in (('ELDER_NPC', 'elder_npc', NPC_BG),
                         ('ELDER_FOCUS', 'elder_focus', FOCUS_BG)):
        a = cutout(src, bg)
        Image.fromarray(a.astype(np.uint8), 'RGBA').save(f'{OUT}/{dst}.png')
        print(f'{OUT}/{dst}.png: {a.shape[1]}x{a.shape[0]}')
    src = Image.open(f'{SRC}/ELDER_ROOM.png').convert('RGBA')
    rgb = np.array(src.convert('RGB')).astype(int)                      # キーせず白枠だけ落とす
    inner = ~((rgb[:, :, 0] > ROOM_WHITE[0]) & (rgb[:, :, 1] > ROOM_WHITE[1]) & (rgb[:, :, 2] > ROOM_WHITE[2]))
    ys, xs = np.where(inner)
    room = src.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    room.save(f'{OUT}/elder_room.png')
    print(f'{OUT}/elder_room.png: {room.width}x{room.height}')

if __name__ == '__main__':
    main()
