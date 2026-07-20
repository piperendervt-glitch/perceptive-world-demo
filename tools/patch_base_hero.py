#!/usr/bin/env python3
# patch_base_hero.py — surgically fix the base (LOD 0/1) hero facing.
#
# The base atlas is NOT on disk: the inline `const SPR=...` (manifest) and
# `ATLAS.src="data:image/png;base64,..."` (atlas PNG) inside index.html are the ONLY
# source of truth. This script:
#   1. extracts inline SPR + base atlas from index.html and decodes the atlas to RGBA
#   2. preserves every non-hero / non-NPC sprite pixel-for-pixel (cropped by SPR coords)
#   3. re-cuts the 9 hero frames from assets/source/hero_3x3.png (same logic as
#      conform_hi.py's hero slice, but fit to ~90px = round(1.6*56), the old base footprint)
#   4. regenerates npc_elder/npc_herb from the NEW hero_down_1 via conform.py's recolor()
#   5. repacks all 34 sprites (conform.py's shelf packer) into a new base atlas + manifest
#   6. rewrites ONLY the inline SPR line and ATLAS.src line in index.html
#      (SPR_HI / ATLAS_HI / draw code / conform.py are left untouched)
import re, json, base64, io
import numpy as np
from PIL import Image

SRC='assets/source'; HTML='index.html'
MAG=(213,60,139)

# ---- helpers copied verbatim from tools/conform_hi.py ----
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
    from scipy import ndimage
    lbl,n=ndimage.label(mask)
    border=set(lbl[0,:]).union(lbl[-1,:]).union(lbl[:,0]).union(lbl[:,-1]); border.discard(0)
    rm=np.isin(lbl,list(border)); out=a.copy(); out[rm,3]=0; return out
def key_bg(a, bg, tol=60, white=196):
    rgb=a[:,:,:3].astype(int)
    d=np.sqrt(((rgb-np.array(bg))**2).sum(2))
    frame=rgb.min(2)>white
    return remove_border_region(a, (d<tol)|frame)

# ---- recolor() copied verbatim from tools/conform.py ----
def recolor(a, hair_rgb=None, tunic_rgb=None):
    o=a.copy(); rgb=o[:,:,:3].astype(int); r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]; al=o[:,:,3]
    mx=rgb.max(2); H=o.shape[0]
    rows=np.arange(H)[:,None]*np.ones((1,o.shape[1]))
    lum=(0.3*r+0.6*g+0.1*b)/255.0
    def paint(mask,to):
        for c in range(3):
            o[:,:,c]=np.where(mask, np.clip(to[c]*(0.5+0.65*lum),0,255).astype(int), o[:,:,c])
    if hair_rgb is not None:
        hair=(al>0)&(r>g)&(g>=b)&(r>55)&(mx<175)&(b<115)&(rows<0.42*H)
        paint(hair, hair_rgb)
    if tunic_rgb is not None:
        tun=(al>0)&(g>r+10)&(g>b+10)
        paint(tun, tunic_rgb)
    return o

# ===== 1. extract inline SPR + base atlas from index.html =====
html=open(HTML,'r',encoding='utf-8',errors='replace').read()
m_spr=re.search(r'^const SPR=(\{.*\});$', html, re.M)
m_atl=re.search(r'^ATLAS\.src="data:image/png;base64,([^"]+)";$', html, re.M)
assert m_spr and m_atl, "could not locate inline base SPR / ATLAS.src"
OLD_SPR=json.loads(m_spr.group(1))
old_atlas=np.array(Image.open(io.BytesIO(base64.b64decode(m_atl.group(1)))).convert('RGBA'))
print(f"base atlas decoded: {old_atlas.shape[1]}x{old_atlas.shape[0]}, {len(OLD_SPR)} sprites")

HERO=[f'hero_{d}_{k}' for d in ('down','up','side') for k in range(3)]
NPC=['npc_elder','npc_herb']

# ===== 2. preserve non-hero/non-NPC sprites, pixel-exact =====
preserved={}
for name,s in OLD_SPR.items():
    if name in HERO or name in NPC: continue
    preserved[name]=old_atlas[s['y']:s['y']+s['h'], s['x']:s['x']+s['w']].copy()

# ===== 3. re-cut hero 9 from hero_3x3.png (fit ~90px) =====
HERO_H=round(1.6*56)   # 90
h3=load('hero_3x3.png'); H,W=h3.shape[:2]; ch,cw=H//3,W//3
dirs=['down','up','side']; heroes={}
for r in range(3):
    for k in range(3):
        cell=h3[r*ch:(r+1)*ch, k*cw:(k+1)*cw]
        cell=key_bg(cell,MAG,tol=70,white=999)                       # magenta key; no white-frame
        dm=np.sqrt(((cell[:,:,:3].astype(int)-np.array(MAG))**2).sum(2))
        cell[dm<45,3]=0                                              # clear enclosed magenta pockets
        heroes[f'hero_{dirs[r]}_{k}']=fit_h(cell, HERO_H)

# ===== 4. regenerate NPCs from the NEW hero_down_1 =====
hero1=heroes['hero_down_1']
npcs={
    'npc_elder':recolor(hero1, hair_rgb=(220,220,224), tunic_rgb=(70,96,200)),   # grey hair, blue robe
    'npc_herb' :recolor(hero1, hair_rgb=(60,42,30),   tunic_rgb=(150,64,168)),   # dark hair, purple robe
}

# ===== 5. repack (conform.py shelf packer), preserving original key order =====
sprites={}
for name in OLD_SPR:                       # keep original ordering
    if name in heroes:   sprites[name]=heroes[name]
    elif name in npcs:   sprites[name]=npcs[name]
    else:                sprites[name]=preserved[name]
assert len(sprites)==len(OLD_SPR)==34, (len(sprites),len(OLD_SPR))

pad=2; maxw_atlas=512; x=pad; y=pad; rowh=0; manifest={}; placed=[]
for name,a in sprites.items():
    hh,ww=a.shape[:2]
    if x+ww+pad>maxw_atlas: x=pad; y+=rowh+pad; rowh=0
    placed.append((name,a,x,y)); manifest[name]={'x':x,'y':y,'w':int(ww),'h':int(hh)}
    x+=ww+pad; rowh=max(rowh,hh)
AW=maxw_atlas; AH=y+rowh+pad
new_atlas=np.zeros((AH,AW,4),np.uint8)
for name,a,px,py in placed:
    hh,ww=a.shape[:2]; new_atlas[py:py+hh, px:px+ww]=a
print(f"new base atlas: {AW}x{AH}, {len(manifest)} sprites")

# ---- verification step 7: preserved sprites are pixel-identical ----
bad=[]
for name in preserved:
    s=manifest[name]; ns=new_atlas[s['y']:s['y']+s['h'], s['x']:s['x']+s['w']]
    if not np.array_equal(ns, preserved[name]): bad.append(name)
assert not bad, f"PRESERVED PIXELS CHANGED: {bad}"
print(f"preservation OK: {len(preserved)} non-hero/non-NPC sprites pixel-identical")

# ===== 6. rewrite inline SPR + ATLAS.src only =====
buf=io.BytesIO(); img(new_atlas).save(buf, format='PNG')
new_b64=base64.b64encode(buf.getvalue()).decode('ascii')
new_spr_line='const SPR='+json.dumps(manifest,separators=(',',':'))+';'
new_atl_line='ATLAS.src="data:image/png;base64,'+new_b64+'";'

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
print(f"index.html patched: SPR({len(manifest)}) + ATLAS.src rewritten; SPR_HI/ATLAS_HI untouched")
print("new hero sizes:", {n:(manifest[n]['w'],manifest[n]['h']) for n in ['hero_down_1','hero_up_1','hero_side_1']})
