import numpy as np, glob, json, os
from PIL import Image
from scipy import ndimage

U='/mnt/user-data/uploads'
OUT='/home/claude/work/assets'; os.makedirs(OUT, exist_ok=True)
def find(p): return glob.glob(os.path.join(U,p+'*'))[0]
CHAR=find('6130dcf9'); TERRAIN=find('e5ba070b'); NATURE=find('bfe0e795')
HOUSE=find('18432b66'); GOBLIN=find('bdd16b95'); INTERIOR=find('5cde8119')

def load(f): return np.array(Image.open(f).convert('RGBA'))
def img(a): return Image.fromarray(a,'RGBA')

def remove_border_region(a, mask):
    """set alpha=0 on mask-True regions connected to the image border."""
    lbl,n=ndimage.label(mask)
    border=set(lbl[0,:]).union(set(lbl[-1,:])).union(set(lbl[:,0])).union(set(lbl[:,-1]))
    border.discard(0)
    rm=np.isin(lbl,list(border))
    out=a.copy(); out[rm,3]=0
    return out

def key_color(a, bg, tol):
    rgb=a[:,:,:3].astype(int)
    d=np.sqrt(((rgb-np.array(bg))**2).sum(2))
    return remove_border_region(a, d<tol)

def key_grey(a, thr=196, spread=14):
    rgb=a[:,:,:3].astype(int)
    mx=rgb.max(2); mn=rgb.min(2)
    mask=((mx-mn)<spread) & (rgb.mean(2)>thr)
    return remove_border_region(a, mask)

def bbox(a, at=24):
    ys,xs=np.where(a[:,:,3]>at)
    return xs.min(),ys.min(),xs.max()+1,ys.max()+1
def crop(a):
    x0,y0,x1,y1=bbox(a); return a[y0:y1,x0:x1]

def despill_green(a):
    """reduce green fringe on kept edge pixels."""
    o=a.copy().astype(int); r,g,b=o[:,:,0],o[:,:,1],o[:,:,2]
    m=(g> r+18)&(g> b+18)&(o[:,:,3]>0)
    o[m,1]=np.maximum(r[m],b[m])+8
    return np.clip(o,0,255).astype(np.uint8)

def fit(a, th, unit=56):
    """downscale cropped sprite to target height th tiles (unit px/tile), keep aspect."""
    a=crop(a); h,w=a.shape[:2]
    H=max(1,round(th*unit)); W=max(1,round(H*w/h))
    im=img(a).resize((W,H), Image.LANCZOS)
    return np.array(im)

def square(a, px=64):
    a=crop(a); im=img(a).resize((px,px), Image.LANCZOS); return np.array(im)

def merge_boxes(boxes):
    """merge only components whose X-ranges overlap (join vertically-stacked parts,
    keep horizontally-separated sprites apart)."""
    def xov(a,b):
        ov=min(a[2],b[2])-max(a[0],b[0])
        if ov<=0: return False
        return ov > 0.35*min(a[2]-a[0], b[2]-b[0])   # only join genuinely stacked parts
    boxes=[list(b) for b in sorted(boxes)]; changed=True
    while changed:
        changed=False; out=[]
        for b in boxes:
            hit=None
            for o in out:
                if xov(o,b): hit=o; break
            if hit:
                hit[0]=min(hit[0],b[0]);hit[1]=min(hit[1],b[1]);hit[2]=max(hit[2],b[2]);hit[3]=max(hit[3],b[3]);changed=True
            else: out.append(b)
        boxes=out
    return sorted(boxes)

def row_objects(a, min_area=1500, gap=None):
    mask=a[:,:,3]>24
    lbl,n=ndimage.label(mask)
    boxes=[]
    for i in range(1,n+1):
        ys,xs=np.where(lbl==i)
        if len(xs)<min_area: continue
        boxes.append((int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)))
    return merge_boxes(boxes)

sprites={}  # name -> np array RGBA

# ---------- terrain: 2x2 grid, grey checker margin ----------
t=key_grey(load(TERRAIN))
x0,y0,x1,y1=bbox(t); t=t[y0:y1,x0:x1]
h,w=t.shape[:2]; mh,mw=h//2,w//2
for name,(r,c) in {'grass':(0,0),'dirt':(0,1),'water':(1,0),'flower':(1,1)}.items():
    cell=t[r*mh:(r+1)*mh, c*mw:(c+1)*mw]
    # inset a little to avoid seam, then square 64
    ins=int(min(mh,mw)*0.04); cell=cell[ins:mh-ins, ins:mw-ins]
    sprites[name]=np.array(img(cell).resize((64,64), Image.LANCZOS))

# ---------- character: 3x3 grid on pure green ----------
c=despill_green(key_color(load(CHAR),(0,255,0),120))
H,W=c.shape[:2]; ch,cw=H//3,W//3
dirs=['down','up','side']
# common frame canvas: find max sprite bbox across cells -> normalize feet to bottom
cells=[[c[r*ch:(r+1)*ch, k*cw:(k+1)*cw] for k in range(3)] for r in range(3)]
# per-cell crop
cropped=[[crop(cells[r][k]) for k in range(3)] for r in range(3)]
maxh=max(cropped[r][k].shape[0] for r in range(3) for k in range(3))
maxw=max(cropped[r][k].shape[1] for r in range(3) for k in range(3))
canW=maxw+8; canH=maxh+8
for r in range(3):
    for k in range(3):
        s=cropped[r][k]; hh,ww=s.shape[:2]
        cv=np.zeros((canH,canW,4),np.uint8)
        ox=(canW-ww)//2; oy=canH-hh-4      # feet aligned near bottom
        cv[oy:oy+hh, ox:ox+ww]=s
        # scale to 1.6 tiles tall
        target_h=round(1.6*56); target_w=round(target_h*canW/canH)
        sprites[f'hero_{dirs[r]}_{k}']=np.array(img(cv).resize((target_w,target_h), Image.LANCZOS))

# ---------- nature row: tree, well, shrine, torch ----------
n=despill_green(key_color(load(NATURE),(131,180,108),95))
boxes=row_objects(n, min_area=1200)
boxes=sorted(boxes)[:4]
names=['tree','well','shrine','torch']; heights=[1.5,1.4,1.3,1.2]
for (bx0,by0,bx1,by1),nm,ht in zip(boxes,names,heights):
    sprites[nm]=fit(n[by0:by1,bx0:bx1], ht)

# ---------- house ----------
hs=despill_green(key_color(load(HOUSE),(132,183,90),100))
sprites['house']=fit(hs, 4.2)

# ---------- goblins row ----------
gb=despill_green(key_color(load(GOBLIN),(132,181,91),100))
gboxes=sorted(row_objects(gb, min_area=1500))[:3]
gnames=['goblin','sentry','chief']; gh=[1.2,1.2,1.9]
for (bx0,by0,bx1,by1),nm,ht in zip(gboxes,gnames,gh):
    sprites[nm]=fit(gb[by0:by1,bx0:bx1], ht)

# ---------- interior: 3 big cells on white (ignore small label text) ----------
it=key_grey(load(INTERIOR), thr=232, spread=16)
iboxes=[b for b in row_objects(it, min_area=9000)]
iboxes=sorted(iboxes)[:3]
inames=['ifloor','iwall','idoor']
for (bx0,by0,bx1,by1),nm in zip(iboxes,inames):
    sprites[nm]=np.array(img(crop(it[by0:by1,bx0:bx1])).resize((64,64), Image.LANCZOS))

# ---------- NPCs: recolor the AI hero (down frame) so they match map style ----------
def recolor(a, hair_rgb=None, tunic_rgb=None):
    o=a.copy(); rgb=o[:,:,:3].astype(int); r,g,b=rgb[:,:,0],rgb[:,:,1],rgb[:,:,2]; al=o[:,:,3]
    mx=rgb.max(2); H=o.shape[0]
    rows=np.arange(H)[:,None]*np.ones((1,o.shape[1]))
    lum=(0.3*r+0.6*g+0.1*b)/255.0
    def paint(mask,to):
        for c in range(3):
            o[:,:,c]=np.where(mask, np.clip(to[c]*(0.5+0.65*lum),0,255).astype(int), o[:,:,c])
    if hair_rgb is not None:
        hair=(al>0)&(r>g)&(g>=b)&(r>55)&(mx<175)&(b<115)&(rows<0.42*H)  # dark brown hair (head region)
        paint(hair, hair_rgb)
    if tunic_rgb is not None:
        tun=(al>0)&(g>r+10)&(g>b+10)                                    # green tunic
        paint(tun, tunic_rgb)
    return o
hero1=sprites['hero_down_1']
sprites['npc_elder']=recolor(hero1, hair_rgb=(220,220,224), tunic_rgb=(70,96,200))   # grey hair, blue robe
sprites['npc_herb'] =recolor(hero1, hair_rgb=(60,42,30),   tunic_rgb=(150,64,168))   # dark hair, purple robe

# ---------- furniture (procedural, warm wood palette to match interior) ----------
def C(w,h): return np.zeros((h,w,4),np.uint8)
def rr(a,x,y,w,h,col):
    x,y,w,h=int(x),int(y),int(w),int(h)
    a[max(0,y):y+h, max(0,x):x+w]=(col[0],col[1],col[2],255)
WD=(139,94,60); WDD=(107,68,35); WDL=(176,128,80); WDLL=(201,157,102)
DK=(60,40,24); IRON=(90,92,100)
U=48
def f_table():
    a=C(U,U); rr(a,6,10,36,28,DK); rr(a,7,11,34,22,WD); rr(a,7,11,34,5,WDL)
    for cx in (8,38):
        rr(a,cx,32,4,10,WDD)
    rr(a,10,14,28,3,WDL); rr(a,10,22,28,2,WDD); return a
def f_chair():
    a=C(U,U); rr(a,14,8,20,6,WDD); rr(a,14,8,20,2,WDL)  # back
    rr(a,13,20,22,10,WD); rr(a,13,20,22,3,WDL)          # seat
    rr(a,14,30,4,10,WDD); rr(a,30,30,4,10,WDD); return a
def f_shelf():  # 1 x 1.4
    a=C(U,int(U*1.4)); H=a.shape[0]; rr(a,4,2,40,H-4,WDD); rr(a,6,4,36,H-8,WD)
    for i,sy in enumerate(range(8,H-10,18)):
        rr(a,6,sy,36,2,WDD)
        cols=[(180,60,60),(60,120,180),(80,160,90),(200,170,70),(150,90,170)]
        bx=8
        for k in range(5):
            bh=12 if (k+i)%2 else 14
            rr(a,bx,sy-bh,4,bh,cols[(k+i)%5]); bx+=6
    rr(a,4,2,40,2,WDL); return a
def f_bed():   # 1 x 2
    a=C(U,U*2); rr(a,4,4,40,U*2-8,WDD)
    rr(a,6,6,36,U*2-12,(190,196,210))               # mattress
    rr(a,8,8,32,26,(230,232,240))                    # pillow area
    rr(a,8,36,32,U*2-44,(150,70,70)); rr(a,8,36,32,4,(180,96,96))  # blanket
    rr(a,4,4,40,3,WDL); return a
def f_plant(): # 1 x 1.2
    a=C(U,int(U*1.2)); H=a.shape[0]; rr(a,14,H-20,20,18,WDD); rr(a,14,H-20,20,4,WDL)
    for (px,py,pw,ph) in [(18,H-46,12,28),(10,H-40,12,20),(26,H-40,12,20),(20,H-52,10,16)]:
        rr(a,px,py,pw,ph,(60,138,60)); rr(a,px,py,pw,3,(90,170,80))
    return a
def f_barrel():
    a=C(U,U); rr(a,10,6,28,38,WD); rr(a,10,6,28,38,WD)
    rr(a,10,6,28,4,WDL); rr(a,10,12,28,3,DK); rr(a,10,34,28,3,DK); rr(a,10,40,28,4,WDD)
    for vx in range(13,38,6): rr(a,vx,10,2,30,WDD)
    return a
def f_cauldron():
    a=C(U,U); rr(a,10,16,28,22,(40,40,46)); rr(a,8,14,32,8,(30,30,36))
    rr(a,12,16,24,5,(90,150,90)); rr(a,14,16,6,3,(150,210,150))    # bubbling liquid
    rr(a,12,38,4,8,(30,30,36)); rr(a,32,38,4,8,(30,30,36))         # legs
    return a
def f_rug():   # 2 x 2
    a=C(U*2,U*2); rr(a,4,4,U*2-8,U*2-8,(150,64,70)); rr(a,10,10,U*2-20,U*2-20,(176,90,96))
    rr(a,4,4,U*2-8,4,(200,150,90)); rr(a,4,U*2-8,U*2-8,4,(200,150,90))
    rr(a,4,4,4,U*2-8,(200,150,90)); rr(a,U*2-8,4,4,U*2-8,(200,150,90))
    for gx in range(20,U*2-16,16): rr(a,gx,U-2,6,4,(210,180,120))
    return a
for nm,fn in [('table',f_table),('chair',f_chair),('shelf',f_shelf),('bed',f_bed),
              ('plant',f_plant),('barrel',f_barrel),('cauldron',f_cauldron),('rug',f_rug)]:
    sprites[nm]=fn()

# ---------- pack atlas ----------
pad=2
items=list(sprites.items())
# simple shelf packing
maxw_atlas=512; x=pad; y=pad; rowh=0; manifest={}
placed=[]
for name,a in items:
    h,w=a.shape[:2]
    if x+w+pad>maxw_atlas: x=pad; y+=rowh+pad; rowh=0
    placed.append((name,a,x,y)); manifest[name]={'x':x,'y':y,'w':int(w),'h':int(h)}
    x+=w+pad; rowh=max(rowh,h)
AW=maxw_atlas; AH=y+rowh+pad
atlas=np.zeros((AH,AW,4),np.uint8)
for name,a,px,py in placed:
    h,w=a.shape[:2]; atlas[py:py+h, px:px+w]=a
img(atlas).save(os.path.join(OUT,'atlas.png'))
json.dump(manifest, open(os.path.join(OUT,'manifest.json'),'w'), indent=0)
print('atlas', AW,'x',AH, 'sprites', len(manifest))
for k in manifest: print(' ',k, manifest[k]['w'],'x',manifest[k]['h'])
# contact preview on dark bg
prev=Image.new('RGBA',(AW,AH),(40,40,50,255)); prev.alpha_composite(img(atlas)); prev.convert('RGB').save(os.path.join(OUT,'preview.png'))
print('done')
