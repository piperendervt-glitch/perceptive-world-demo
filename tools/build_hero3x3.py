#!/usr/bin/env python3
# build_hero3x3.py — assemble a normalized hero_3x3.png from the 3 magenta-bg bands
# (hero_down/up/side.png, each 3 frames). Removes magenta bg + navy cell frames,
# detects the 3 characters per band, normalizes to a common height (feet-aligned),
# reorders frames [stand,walkA,walkB] -> [walkA,stand,walkB], writes assets/source/hero_3x3.png.
import numpy as np
from PIL import Image
from scipy import ndimage

MAG=np.array([213,60,139])
def load(f): return np.array(Image.open(f'assets/source/hero_{f}.png').convert('RGB')).astype(int)

def band_mask(a, magtol=60):
    # remove magenta bg + navy cell frames. Frame lines are long, perfectly-straight
    # runs of near-black (verticals ~cell height, horizontals ~cell width). The character
    # outline curves, and its legs/belt are far shorter, so straight-line openings isolate
    # only the frame. Applied to raw near_black so thick lines (ground line) are caught too.
    ismag=np.sqrt(((a-MAG)**2).sum(2))<magtol
    near_black=(a.mean(2)<85)&(~ismag)
    vframe=ndimage.binary_opening(near_black, structure=np.ones((320,1)))  # vertical borders
    hframe=ndimage.binary_opening(near_black, structure=np.ones((1,260)))  # horizontal borders / ground line
    frame=ndimage.binary_dilation(vframe|hframe, iterations=2)
    fg=(~ismag)&(~frame)
    lbl,n=ndimage.label(fg); sz=ndimage.sum(np.ones_like(lbl),lbl,range(1,n+1))
    keep=np.zeros_like(fg)
    for i,s in enumerate(sz,1):
        if s>=500: keep|=(lbl==i)
    return keep

def crops_for(d):
    a=load(d); m=band_mask(a); W=a.shape[1]; out=[]
    for k in range(3):
        x0,x1=k*W//3,(k+1)*W//3; sub=m[:,x0:x1].copy()
        # keep only the largest connected component (the character) -> drops frame/speck remnants
        lbl,n=ndimage.label(sub)
        if n>1:
            sz=ndimage.sum(np.ones_like(lbl),lbl,range(1,n+1)); big=int(np.argmax(sz))+1
            sub=(lbl==big)
        m[:,x0:x1]=sub
        ys,xs=np.where(sub)
        bx=(x0+int(xs.min()),int(ys.min()),x0+int(xs.max())+1,int(ys.max())+1)
        rgb=a[bx[1]:bx[3],bx[0]:bx[2]].astype(np.uint8)
        al=(m[bx[1]:bx[3],bx[0]:bx[2]]*255).astype(np.uint8)
        rgb=rgb.copy(); rgb[al==0]=MAG      # kill dark fringe -> magenta so scaling is clean
        out.append((rgb,al))
    return out

bands={d:crops_for(d) for d in ['down','up','side']}
Hmax=max(al.shape[0] for d in bands for _,al in bands[d])
print("Hmax(char height) =",Hmax)

# scale each char to height Hmax (preserve aspect)
def scale_to_h(rgb,al,H):
    h,w=al.shape; W=max(1,round(H*w/h))
    im=Image.fromarray(np.dstack([rgb,al]),'RGBA').resize((W,H),Image.LANCZOS)
    return np.array(im)
scaled={d:[scale_to_h(rgb,al,Hmax) for rgb,al in bands[d]] for d in bands}
maxW=max(s.shape[1] for d in scaled for s in scaled[d])

PAD_TOP=8; PAD_BOT=8; PAD_X=10
cellH=Hmax+PAD_TOP+PAD_BOT; cellW=maxW+2*PAD_X
print("cell =",cellW,"x",cellH,"sheet =",cellW*3,"x",cellH*3)

order=[1,0,2]   # [stand,walkA,walkB] -> [walkA,stand,walkB]
rows=['down','up','side']
sheet=Image.new('RGBA',(cellW*3,cellH*3),(MAG[0],MAG[1],MAG[2],255))
for r,d in enumerate(rows):
    frames=scaled[d]
    for outc,src in enumerate(order):
        s=frames[src]; sh,sw=s.shape[:2]
        ox=outc*cellW+(cellW-sw)//2
        oy=r*cellH+(cellH-PAD_BOT-sh)        # feet aligned to cell bottom
        sheet.alpha_composite(Image.fromarray(s,'RGBA'),(ox,oy))
sheet.convert('RGB').save('assets/source/hero_3x3.png')
print("wrote assets/source/hero_3x3.png (uniform magenta bg)")
