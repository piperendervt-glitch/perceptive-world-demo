#!/usr/bin/env python3
# patch_base_shrine.py — surgically swap the base (LOD 0/1) `shrine` sprite.
#
# Same method as tools/patch_base_hero.py: the base atlas is NOT on disk, the inline
# `const SPR=...` + `ATLAS.src="data:image/png;base64,..."` in index.html are the only
# source of truth. This script:
#   1. extracts inline SPR + base atlas from index.html
#   2. preserves EVERY other sprite pixel-for-pixel (hero_* 9 frames included)
#   3. re-cuts `shrine` from assets/source/shrine_base.png (magenta key + drop-shadow removal)
#   4. fits it to the old shrine footprint and pads it back to the old cell size, so the
#      square PROP['H'] draw box (1.35 x 1.35 tiles) keeps the art undistorted and anchored
#   5. repacks (conform.py shelf packer) and rewrites ONLY the SPR / ATLAS.src lines
import re, json, base64, io
import numpy as np
from PIL import Image
from scipy import ndimage

SRC='assets/source'; HTML='index.html'
BG=(229,24,135)          # measured magenta background of shrine_base.png

def load(f): return np.array(Image.open(f'{SRC}/{f}').convert('RGBA'))
def img(a): return Image.fromarray(a.astype(np.uint8),'RGBA')
def bbox(a,at=24):
    ys,xs=np.where(a[:,:,3]>at); return xs.min(),ys.min(),xs.max()+1,ys.max()+1
def crop(a):
    x0,y0,x1,y1=bbox(a); return a[y0:y1,x0:x1]
def fit_h(a,H):
    a=crop(a); h,w=a.shape[:2]; W=max(1,round(H*w/h))
    return np.array(img(a).resize((W,int(H)), Image.LANCZOS))
def remove_border_region(a, mask):
    lbl,n=ndimage.label(mask)
    border=set(lbl[0,:]).union(lbl[-1,:]).union(lbl[:,0]).union(lbl[:,-1]); border.discard(0)
    rm=np.isin(lbl,list(border)); out=a.copy(); out[rm,3]=0; return out
def key_bg(a, bg, tol=60, white=196):
    rgb=a[:,:,:3].astype(int)
    d=np.sqrt(((rgb-np.array(bg))**2).sum(2))
    frame=rgb.min(2)>white
    return remove_border_region(a, (d<tol)|frame)
def drop_pink(a):
    """kill the drop shadow + any magenta-family fringe (stone/moss/rope/shide are safe)"""
    rgb=a[:,:,:3].astype(int); r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]
    o=a.copy(); o[(o[:,:,3]>0)&(r>g+40)&(b>g+20),3]=0; return o
def pad_to(a,W,H):
    """centre horizontally, bottom-align (matches blitAnchor's anchor)"""
    h,w=a.shape[:2]; out=np.zeros((H,W,4),np.uint8)
    x=(W-w)//2; y=H-h
    out[y:y+h, x:x+w]=a; return out

# ===== 1. extract inline SPR + base atlas =====
html=open(HTML,'r',encoding='utf-8',errors='replace').read()
m_spr=re.search(r'^const SPR=(\{.*\});$', html, re.M)
m_atl=re.search(r'^ATLAS\.src="data:image/png;base64,([^"]+)";$', html, re.M)
assert m_spr and m_atl, "could not locate inline base SPR / ATLAS.src"
OLD_SPR=json.loads(m_spr.group(1))
old_atlas=np.array(Image.open(io.BytesIO(base64.b64decode(m_atl.group(1)))).convert('RGBA'))
OW,OH=OLD_SPR['shrine']['w'], OLD_SPR['shrine']['h']
print(f"base atlas decoded: {old_atlas.shape[1]}x{old_atlas.shape[0]}, {len(OLD_SPR)} sprites; old shrine {OW}x{OH}")

# ===== 2. preserve every sprite except `shrine` =====
preserved={}
for name,s in OLD_SPR.items():
    if name=='shrine': continue
    preserved[name]=old_atlas[s['y']:s['y']+s['h'], s['x']:s['x']+s['w']].copy()

# ===== 3. re-cut shrine from the new base art =====
a=drop_pink(key_bg(load('shrine_base.png'), BG, tol=70, white=999))
shrine=pad_to(fit_h(a, OH), OW, OH)      # same cell size as before -> same on-screen box
print(f"new shrine cell {shrine.shape[1]}x{shrine.shape[0]} (art fitted to h={OH}, padded to w={OW})")

# ===== 4. repack, preserving original key order =====
sprites={n:(shrine if n=='shrine' else preserved[n]) for n in OLD_SPR}
assert len(sprites)==len(OLD_SPR)
pad=2; maxw_atlas=512; x=y=pad; rowh=0; manifest={}; placed=[]
for name,arr in sprites.items():
    hh,ww=arr.shape[:2]
    if x+ww+pad>maxw_atlas: x=pad; y+=rowh+pad; rowh=0
    placed.append((arr,x,y)); manifest[name]={'x':x,'y':y,'w':int(ww),'h':int(hh)}
    x+=ww+pad; rowh=max(rowh,hh)
AW,AH=maxw_atlas, y+rowh+pad
new_atlas=np.zeros((AH,AW,4),np.uint8)
for arr,px,py in placed:
    hh,ww=arr.shape[:2]; new_atlas[py:py+hh, px:px+ww]=arr
print(f"new base atlas: {AW}x{AH}, {len(manifest)} sprites")

# ---- verification: every other sprite is pixel-identical ----
bad=[n for n in preserved
     if not np.array_equal(new_atlas[manifest[n]['y']:manifest[n]['y']+manifest[n]['h'],
                                     manifest[n]['x']:manifest[n]['x']+manifest[n]['w']], preserved[n])]
assert not bad, f"PRESERVED PIXELS CHANGED: {bad}"
print(f"preservation OK: {len(preserved)} sprites pixel-identical (hero_* included)")

# ===== 5. rewrite inline SPR + ATLAS.src only =====
buf=io.BytesIO(); img(new_atlas).save(buf, format='PNG')
new_spr_line='const SPR='+json.dumps(manifest,separators=(',',':'))+';'
new_atl_line='ATLAS.src="data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode('ascii')+'";'
lines=html.split('\n')
spr_hi_before=[l for l in lines if l.startswith('const SPR_HI=')]
atlas_hi_before=[l for l in lines if l.startswith('ATLAS_HI.src=')]
ns=na=0
for i,l in enumerate(lines):
    if l.startswith('const SPR='):   lines[i]=new_spr_line; ns+=1
    elif l.startswith('ATLAS.src='): lines[i]=new_atl_line; na+=1
assert ns==1 and na==1, (ns,na)
new_html='\n'.join(lines); nl=new_html.split('\n')
assert [l for l in nl if l.startswith('const SPR_HI=')]==spr_hi_before, "SPR_HI changed!"
assert [l for l in nl if l.startswith('ATLAS_HI.src=')]==atlas_hi_before, "ATLAS_HI changed!"
open(HTML,'w',encoding='utf-8',newline='').write(new_html)
print("index.html patched: SPR + ATLAS.src rewritten; SPR_HI/ATLAS_HI untouched")
