"""Draw the four offerings (sugar, wormwood, feather, candle smoke) as an SVG sprite
of engraved line art, for web/index.html.

    python scripts/engrave_offerings.py sprite.svg
"""
import math, random
def bez(p0,p1,p2,p3,t):
    return tuple((1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d for a,b,c,d in zip(p0,p1,p2,p3))
def tangent(p0,p1,p2,p3,t,e=1e-3):
    a=bez(p0,p1,p2,p3,max(0,t-e)); b=bez(p0,p1,p2,p3,min(1,t+e)); dx,dy=b[0]-a[0],b[1]-a[1]; n=math.hypot(dx,dy); return dx/n,dy/n
f=lambda v: f"{v:.1f}"
out=[]
# sugar: a cube of sugar, stippled like an engraving, with loose grains
random.seed(7)
top=[(32,14),(50,23),(32,32),(14,23)]
L=[(14,23),(32,32),(32,52),(14,43)]; R=[(32,32),(50,23),(50,43),(32,52)]
poly=lambda p: "M"+" L".join(f"{f(x)} {f(y)}" for x,y in p)+"Z"
s=[f'<path d="{poly(top)}"/>',f'<path d="{poly(L)}"/>',f'<path d="{poly(R)}"/>']
def stipple(face,n):
    (ax,ay),(bx,by),(cx,cy),(dx,dy)=face
    pts=[]
    for _ in range(n):
        u,v=random.uniform(.08,.92),random.uniform(.08,.92)
        x=ax+(bx-ax)*u+(dx-ax)*v; y=ay+(by-ay)*u+(dy-ay)*v
        pts.append(f"M{f(x)} {f(y)}h0.01")
    return f'<path class="d" d="{"".join(pts)}"/>'
s.append(stipple(top,14)); s.append(stipple(L,30)); s.append(stipple(R,70))
for x,y in [(55,50),(58,46),(9,52),(53,56),(12,57)]:
    s.append(f'<path d="M{x} {y-1.4} l1.4 1.4 l-1.4 1.4 l-1.4 -1.4z"/>')
out.append(("nectar",s))
# wormwood sprig: stem with pinnately lobed leaves
P=((30,61),(26,44),(36,28),(38,5)); s=[f'<path d="M30 61 C26 44, 36 28, 38 5"/>']
for k,t in enumerate([0.18,0.3,0.42,0.54,0.66,0.78,0.9]):
    x,y=bez(*P,t); tx,ty=tangent(*P,t); side=-1 if k%2==0 else 1
    nx,ny=-ty*side,tx*side; size=14*(1-t*0.6)
    # leaf blade slanting upward from the stem, with two lobes
    ex,ey=x+nx*size+tx*size*0.55,y+ny*size+ty*size*0.55
    mx,my=(x+ex)/2,(y+ey)/2
    w=size*0.28
    s.append(f'<path d="M{f(x)} {f(y)} Q{f(mx+tx*w*2)} {f(my+ty*w*2)} {f(ex)} {f(ey)} Q{f(mx-tx*w*1.4)} {f(my-ty*w*1.4)} {f(x)} {f(y)}"/>')
    s.append(f'<path class="h" d="M{f(x)} {f(y)} L{f(ex)} {f(ey)}"/>')
    # a side lobe
    lx,ly=x+nx*size*0.45+tx*size*0.15,y+ny*size*0.45+ty*size*0.15
    s.append(f'<path class="h" d="M{f(lx)} {f(ly)} q{f(tx*size*0.5)} {f(ty*size*0.5)} {f(tx*size*0.55+nx*2)} {f(ty*size*0.55+ny*2)}"/>')
out.append(("bitter",s))
# feather: rachis with bare quill; each vane drawn as an outline, barbs sparse and soft
P=((10,62),(22,42),(36,22),(54,6)); s=[f'<path d="M10 62 C22 42, 36 22, 54 6"/>']
for side,width in ((1,13),(-1,8)):
    edge=[]
    for i in range(15):
        t=0.22+i*0.054; x,y=bez(*P,min(t,1)); tx,ty=tangent(*P,min(t,1))
        env=math.sin(math.pi*min(1,(t-0.2)/0.82))**0.6
        nx,ny=-ty*side,tx*side; ln=width*env+0.6
        ex,ey=x+(nx*0.7+tx*0.7)*ln,y+(ny*0.7+ty*0.7)*ln
        edge.append((ex,ey))
        if i%2==0 and not (side==-1 and i==6):
            s.append(f'<path class="h" d="M{f(x)} {f(y)} Q{f(x+nx*ln*0.6)} {f(y+ny*ln*0.6)} {f(ex)} {f(ey)}"/>')
    x0,y0=bez(*P,0.2)
    s.append(f'<path d="M{f(x0)} {f(y0)} '+" ".join(("L" if k else "Q")+f"{f(x)} {f(y)}" if k else f"L{f(x)} {f(y)}" for k,(x,y) in enumerate(edge))+'"/>')
out.append(("touch",s))
# breath: a slim snuffed candle and its curling smoke
s=['<path d="M27 46 L27 62 M37 46 L37 62 M24 62 L40 62"/>','<path d="M27 46 Q32 44 37 46"/>','<path d="M34 46.5 q1.2 3.5 0.4 7.5 q-0.3 1.4 -0.9 0"/>',
   '<path d="M32 45 L32 41"/>',
   '<path d="M32 41 C27 35, 37 31, 32 25 S26 14, 32 8 S38 3, 35 1"/>',
   '<path class="h" d="M33 38 C39 33, 31 28, 37 21 S43 12, 39 6"/>',
   '<path class="h" d="M31 37 C25 32, 29 25, 25 19 S22 12, 25 8"/>']
for i in range(4): s.append(f'<path class="h" d="M{f(34.5+i*0.7)} {48+i} L{f(34.5+i*0.7)} 61"/>')
out.append(("breath",s))
svg=['<svg class="sprite" aria-hidden="true" focusable="false">']
for name,paths in out:
    svg.append(f'  <symbol id="gift-{name}" viewBox="0 0 64 64">'+"".join(paths)+'</symbol>')
svg.append('</svg>')
open(__import__('sys').argv[1],'w').write("\n".join(svg)+"\n")
