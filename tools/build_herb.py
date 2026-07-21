#!/usr/bin/env python3
# build_herb.py — 薬草小屋の詳細度 +2/+3 用の独立画像を作る（アトラス外）。build_elder.py の対の実装。
#   assets/source/HERB_NPC.png   (マゼンタ背景) → 透過 → assets/focus/herb_npc.png   … +2 の薬師ちび
#   assets/source/HERB_FOCUS.png (マゼンタ背景) → 透過 → assets/focus/herb_focus.png … +3 の薬師全身
#   assets/source/HERB_ROOM.png  (濃紺枠つき内装) → 枠クロップのみ（キーしない）
#                                                → assets/focus/herb_room.png  … +2 の背景（下辺中央が扉）
# ※ atlas.png / atlas_hi.png / well_focus / shrine_focus / tower_* / elder_* には一切触れない。
import numpy as np
from PIL import Image
from scipy import ndimage

SRC = 'assets/source'; OUT = 'assets/focus'
NPC_BG   = (232, 27, 148)   # HERB_NPC の実測マゼンタ背景
FOCUS_BG = (221, 61, 158)   # HERB_FOCUS の実測マゼンタ背景
ROOM_NAVY = (29, 31, 45)    # HERB_ROOM の枠色（これに近い＝枠）
ROOM_TOL  = 60              # 枠判定のしきい値。部屋 bbox は実測 (21,20)-(1004,1024)

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
    """マゼンタ系のフリンジ／影を除去。
    薬師は藤色のローブなので、村長（青ローブ）より判定を厳しくして本体を守る:
      * 赤が緑を大きく上回り、かつ青も緑より高い（＝マゼンタ）
      * 背景マゼンタの色相に十分近いものだけ"""
    rgb = a[:, :, :3].astype(int); r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    o = a.copy()
    o[(o[:, :, 3] > 0) & (r > g + 90) & (b > g + 40) & (r > 150), 3] = 0
    return o

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
    for src, dst, bg in (('HERB_NPC', 'herb_npc', NPC_BG),
                         ('HERB_FOCUS', 'herb_focus', FOCUS_BG)):
        a = cutout(src, bg)
        Image.fromarray(a.astype(np.uint8), 'RGBA').save(f'{OUT}/{dst}.png')
        print(f'{OUT}/{dst}.png: {a.shape[1]}x{a.shape[0]}')
    src = Image.open(f'{SRC}/HERB_ROOM.png').convert('RGBA')
    rgb = np.array(src.convert('RGB')).astype(int)                      # キーせず枠だけ落とす
    inner = np.sqrt(((rgb - np.array(ROOM_NAVY)) ** 2).sum(2)) > ROOM_TOL
    ys, xs = np.where(inner)
    room = src.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))
    room.save(f'{OUT}/herb_room.png')
    print(f'{OUT}/herb_room.png: {room.width}x{room.height}')

if __name__ == '__main__':
    main()
