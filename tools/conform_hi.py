#!/usr/bin/env python3
# conform_hi.py — 詳細度+2 用の高精細アトラスを生成する。
# assets/source/ の 1024px 素材（Nano Banana 出力）を透過・切出しし、
# 縮小しすぎない大きめサイズで assets/hi/atlas_hi.png + manifest_hi.json を出力する。
import os, json, numpy as np
from PIL import Image
from scipy import ndimage

SRC='assets/source'; OUT='assets/hi'; os.makedirs(OUT, exist_ok=True)
def load(f): return np.array(Image.open(os.path.join(SRC,f)).convert('RGBA'))
def img(a): return Image.fromarray(a.astype(np.uint8),'RGBA')

def remove_border_region(a, mask):
    lbl,n=ndimage.label(mask)
    border=set(lbl[0,:]).union(lbl[-1,:]).union(lbl[:,0]).union(lbl[:,-1]); border.discard(0)
    rm=np.isin(lbl,list(border)); out=a.copy(); out[rm,3]=0; return out

def key_bg(a, bg, tol=60, white=196):
    rgb=a[:,:,:3].astype(int)
    d=np.sqrt(((rgb-np.array(bg))**2).sum(2))
    frame=rgb.min(2)>white                      # white cell/frame border
    return remove_border_region(a, (d<tol)|frame)

def despill_green(a):
    o=a.copy().astype(int); r,g,b=o[:,:,0],o[:,:,1],o[:,:,2]
    m=(g>r+18)&(g>b+18)&(o[:,:,3]>0); o[m,1]=np.maximum(r[m],b[m])+8
    return np.clip(o,0,255).astype(np.uint8)

def bbox(a,at=24):
    ys,xs=np.where(a[:,:,3]>at); return xs.min(),ys.min(),xs.max()+1,ys.max()+1
def crop(a):
    x0,y0,x1,y1=bbox(a); return a[y0:y1,x0:x1]
def fit_h(a,H):
    a=crop(a); h,w=a.shape[:2]; W=max(1,round(H*w/h))
    return np.array(img(a).resize((W,int(H)), Image.LANCZOS))

sprites={}

# ---------- terrain 2x2 (no keying: 4 full-bleed textures) ----------
t=load('terrain_2x2.png'); H,W=t.shape[:2]; mh,mw=H//2,W//2
grid={'grass':(0,0),'dirt':(0,1),'water':(1,0),'flower':(1,1)}
for name,(r,c) in grid.items():
    cell=t[r*mh:(r+1)*mh, c*mw:(c+1)*mw]
    ins=int(min(mh,mw)*0.03); cell=cell[ins:mh-ins, ins:mw-ins]
    sprites[name]=np.array(img(cell).resize((128,128), Image.LANCZOS))

# ---------- hero 3x3 (green bg + white cell frames) ----------
h=load('hero_3x3.png'); H,W=h.shape[:2]; ch,cw=H//3,W//3
dirs=['down','up','side']
for r in range(3):
    for k in range(3):
        cell=h[r*ch:(r+1)*ch, k*cw:(k+1)*cw]
        cell=despill_green(key_bg(cell,(112,149,45),tol=64))
        sprites[f'hero_{dirs[r]}_{k}']=fit_h(cell, 220)

# ---------- well / tree (green bg + white frame) ----------
sprites['well']=fit_h(despill_green(key_bg(load('well.png'),(137,162,87),tol=58)), 210)
sprites['tree']=fit_h(despill_green(key_bg(load('tree.png'),(136,184,78),tol=58)), 230)

# ---------- pack atlas ----------
pad=2; maxw=1024; x=y=pad; rowh=0; manifest={}; placed=[]
for name,a in sorted(sprites.items()):
    hh,ww=a.shape[:2]
    if x+ww+pad>maxw: x=pad; y+=rowh+pad; rowh=0
    placed.append((a,x,y)); manifest[name]={'x':x,'y':y,'w':int(ww),'h':int(hh)}
    x+=ww+pad; rowh=max(rowh,hh)
AW,AH=maxw, y+rowh+pad
atlas=np.zeros((AH,AW,4),np.uint8)
for a,px,py in placed:
    hh,ww=a.shape[:2]; atlas[py:py+hh, px:px+ww]=a
img(atlas).save(os.path.join(OUT,'atlas_hi.png'))
json.dump(manifest, open(os.path.join(OUT,'manifest_hi.json'),'w'), indent=0)
print('atlas_hi', AW,'x',AH,'sprites',len(manifest))
for k in manifest: print(' ',k, manifest[k]['w'],'x',manifest[k]['h'])
Image.new('RGBA',(AW,AH),(40,40,50,255)).__class__  # noop
prev=Image.new('RGBA',(AW,AH),(40,40,50,255)); prev.alpha_composite(img(atlas)); prev.convert('RGB').save(os.path.join(OUT,'preview_hi.png'))
print('done')
