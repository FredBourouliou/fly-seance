"""Build the attributed, articulated Sketchfab specimen. Blender 5.2, no addons/network.
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup -b -P web/fly/build_scan.py
Source is opened read-only. All products and temporary files stay in web/fly/.
Use -- --no-render to omit the diagnostic segmentation plates.
"""
import bpy, bmesh, numpy as np, math, json, pathlib, os, sys, hashlib, struct
from mathutils import Vector, Matrix, Quaternion
from mathutils.kdtree import KDTree
from collections import defaultdict
HERE=pathlib.Path(__file__).resolve().parent
os.environ['TMPDIR']=str(HERE)
bpy.context.preferences.filepaths.temporary_directory=str(HERE)
sys.path.insert(0,str(HERE))
from inspect_scan import source_arrays, SOURCE
CREDIT='''This work is based on "Wildtype Female Drosophila Melanogaster"
(https://sketchfab.com/3d-models/wildtype-female-drosophila-melanogaster-3ba1adba62f34fe995413ee5e9cf3c25)
by mlykouretzos (https://sketchfab.com/mlykouretzos), licensed under CC-BY-4.0
(http://creativecommons.org/licenses/by/4.0/). Modified: decimated, segmented,
rigged, proboscis extended, materials changed. Rigging and code generated with
OpenAI Codex for Fly Séance.'''
(HERE/'MODEL-LICENSE.txt').write_text(CREDIT+'\n')
(HERE/'renders').mkdir(exist_ok=True)
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene;scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=.001
raw,colors,faces,components=source_arrays()
source_triangles=len(faces)
valid=(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,0]!=faces[:,2])
faces=faces[valid]
_,unique=np.unique(np.sort(faces,axis=1),axis=0,return_index=True);faces=faces[np.sort(unique)]
print('Welded source',len(raw),len(faces),'components',int(components.max()+1),flush=True)
# A pitched natural resting thorax: raw +Z up/-Y front is retained. No reflection.
SCALE=2.5/9.2521; CENTER=np.array([1.0358,3.,0.]); ROT=Matrix.Rotation(math.radians(18),3,'X'); R=np.array(ROT)
def world(p):return (np.asarray(p)-CENTER)@R.T*SCALE+np.array([0,0,.65])
verts=world(raw); fc=raw[faces].mean(1); fl=components[faces[:,0]]
nodes={}; origins={}; meshes=[]; rig={'version':2,'source':'Sketchfab/mlykouretzos','units':'mm','joints':{},'legs':[],'tableY':0}
IDENT=Quaternion()
def qjson(q):return [q.x,q.z,-q.y,q.w]
def vecjson(p):return [float(p[0]),float(p[2]),float(-p[1])]
def node(name,parent=None,origin=(0,0,0)):
    o=bpy.data.objects.new(name,None);scene.collection.objects.link(o);nodes[name]=o;origins[name]=Vector(origin)
    if parent:o.parent=nodes[parent];o.location=Vector(origin)-origins[parent]
    else:o.location=origin
    o.rotation_mode='QUATERNION';return o
node('fly_root');nodes['fly_root']['attribution']=CREDIT;node('body_posture','fly_root')
node('head','body_posture',world([1.0358,.88,.82]))
for side,sign in [('L',1),('R',-1)]:
    node('antenna_'+side,'head',world([1.0358+sign*.46,-.70,1.05]))
node('abdomen','body_posture')
MAT={}
for key in ['cuticle','leg','eye','ocellus','wing','hair','oral']:
    m=bpy.data.materials.new(key);m.use_nodes=True;p=m.node_tree.nodes.get('Principled BSDF');p.inputs['Roughness'].default_value=.85 if key=='eye' else .48
    a=m.node_tree.nodes.new('ShaderNodeVertexColor');a.layer_name='Color';m.node_tree.links.new(a.outputs['Color'],p.inputs['Base Color']);MAT[key]=m

def create_mesh(name,parent,v,f,c,key,ratio=1):
    if not len(f):return
    print('mesh',name,len(f),round(ratio,3),flush=True)
    me=bpy.data.meshes.new(name);me.from_pydata(np.asarray(v).tolist(),[],np.asarray(f).tolist());me.update()
    ob=bpy.data.objects.new(name,me);scene.collection.objects.link(ob);ob.parent=nodes[parent];me.materials.append(MAT[key]);meshes.append(ob)
    attr=me.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='POINT');attr.data.foreach_set('color',np.asarray(c,dtype=np.float32).ravel())
    # Cap only boundaries introduced by anatomical cuts; source hairs are already closed.
    if key not in ('hair','wing'):
        bm=bmesh.new();bm.from_mesh(me)
        if key=='eye' and name.endswith('__eye'):
            # The source eye has folded internal triangles near its rim. Reuse its
            # coloured outer vertices in a closed convex ocular surface.
            bmesh.ops.delete(bm,geom=list(bm.edges),context='EDGES_FACES')
            bmesh.ops.convex_hull(bm,input=list(bm.verts),use_existing_faces=False)
            unused=[v for v in bm.verts if not v.link_faces]
            if unused:bmesh.ops.delete(bm,geom=unused,context='VERTS')
        edges=[e for e in bm.edges if e.is_boundary]
        if edges:bmesh.ops.holes_fill(bm,edges=edges,sides=0)
        bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
        bmesh.ops.triangulate(bm,faces=list(bm.faces))
        bm.to_mesh(me);bm.free()
    bpy.context.view_layer.objects.active=ob;ob.select_set(True)
    if ratio<1:
        mod=ob.modifiers.new('Silhouette-preserving collapse','DECIMATE');mod.ratio=ratio;mod.use_collapse_triangulate=True
        bpy.ops.object.modifier_apply(modifier=mod.name)
    ob.data.validate(verbose=False,clean_customdata=False)
    for p in ob.data.polygons:p.use_smooth=True
    ob.select_set(False);return ob

def smooth(a,b,x):
    t=np.clip((x-a)/(b-a),0,1);return t*t*(3-2*t)

def pigment(r,c,parent,key):
    """Anatomical pigments in linear RGB, with the source's painted plate boundaries.
    Source mouth colours are deliberately left intact. No photograph is sampled.
    """
    out=c.copy();old=c[:,:3];x,y,z=r.T
    if key=='cuticle':
        variation=.68+.45*smooth(.43,.83,old[:,0])
        if parent=='abdomen':
            abdomen=smooth(3.4,4.3,y);dorsal=smooth(-.4,1.6,z)
            thorax=np.array([.31,.172,.075])*(1-dorsal[:,None])+np.array([.205,.071,.029])*dorsal[:,None]
            belly=smooth(.40,.56,old[:,1])*(1-smooth(-.6,.65,z))
            tail=smooth(5.5,8.05,y)*(1-belly)
            tergite=np.array([.29,.170,.068])*(1-.52*tail[:,None])
            abdomen_color=tergite*(1-belly[:,None])+np.array([.43,.355,.205])*belly[:,None]
            band=1-smooth(.17,.42,old[:,0])
            abdomen_color=abdomen_color*(1-band[:,None])+np.array([.018,.010,.005])*band[:,None]
            col=thorax*(1-abdomen[:,None])+abdomen_color*abdomen[:,None]
        else:
            dorsal=smooth(.15,1.9,z)
            col=np.array([.32,.219,.115])*(1-dorsal[:,None])+np.array([.21,.120,.057])*dorsal[:,None]
        out[:,:3]=col*variation[:,None]
    elif key=='leg':
        variation=.76+.32*smooth(.60,.79,old[:,0])
        proximal=smooth(-2.0,-.4,z)
        col=np.array([.40,.285,.160])*(1-proximal[:,None])+np.array([.26,.145,.062])*proximal[:,None]
        out[:,:3]=col*variation[:,None]
        # Source darker pigment at cuticular joints stays visible through the pale tan.
        joint=1-smooth(.607,.642,old[:,0]);out[:,:3]*=(1-.27*joint[:,None])
        for sign in [-1,1]:
            for j in [[1.53,2.55,-1.16],[2.88,1.10,-1.48],[3.19,.72,-3.08]]:
                j=np.array(j);j[0]=1.0358+sign*(j[0]-1.0358)
                crease=np.exp(-np.sum((r-j)**2,axis=1)/(.20**2))
                out[:,:3]*=1-.38*crease[:,None]
    elif key=='eye':
        radial=np.sqrt(((y+.0052)/.62)**2+((z-.9)/.72)**2)
        rim=smooth(.72,1.00,radial)
        out[:,:3]=np.array([.235,.019,.012])*(1-.47*rim[:,None])
    elif key=='ocellus':out[:,:3]=np.array([.035,.019,.005])
    elif key=='hair':out[:,:3]*=np.array([.25,.25,.29])
    return out

def subset(name,parent,mask,key,ratio=1,transform=None):
    ff=faces[mask];ids,ix=np.unique(ff,return_inverse=True);v=verts[ids].copy();c=colors[ids].copy()
    if transform is not None:v=transform(v,raw[ids])
    c=pigment(raw[ids],c,parent,key)
    return create_mesh(name,parent,v-np.array(origins[parent]),ix.reshape(-1,3),c,key,ratio)

# Connected head and source mouth/antennae are spatially divided at their sockets.
headmask=fl==120
mouthmask=headmask & (fc[:,2]<-.18) & (np.abs(fc[:,0]-1.0358)<.49)
antenna_masks={}
for side,sign in [('L',1),('R',-1)]:
    antenna_masks[side]=headmask & (fc[:,1]<-.77) & (fc[:,2]>.40)&(fc[:,2]<1.15)&((fc[:,0]-1.0358)*sign>.21)&((fc[:,0]-1.0358)*sign<.75)
    subset('antenna_'+side+'__cuticle','antenna_'+side,antenna_masks[side],'cuticle',.85)
subset('head__cuticle','head',headmask & ~mouthmask & ~antenna_masks['L'] & ~antenna_masks['R'],'cuticle',.45)
# Resolve the source's almost coplanar eye/face overlap without changing its eye topology.
def fit_eye(v,r):
    sign=np.where(r[:,0]>1.0358,1.,-1.);centers=world(np.column_stack((1.0358+sign*.9637,np.full(len(r),-.0052),np.full(len(r),.9))))
    return centers+(v-centers)*1.035+np.column_stack((sign*.006,np.zeros(len(r)),np.zeros(len(r))))
subset('head_L__eye','head',fl==147,'eye',1,fit_eye)
subset('head_R__eye','head',fl==86,'eye',1,fit_eye)
def fit_ocelli(v,r):
    out=v.copy()
    for center in [raw[components==i].mean(0) for i in [116,117,118]]:
        m=np.linalg.norm(r-center,axis=1)<.085;out[m]=world(center)+.65*(v[m]-world(center))
    return out
subset('head__ocelli','head',np.isin(fl,[116,117,118]),'ocellus',.38,fit_ocelli)
subset('thorax_abdomen__cuticle','abdomen',fl==146,'cuticle',.22)
# Fold each complete wing about its intact hinge. Geometry and painted venation travel together.
for side,sign,cid in [('L',1,183),('R',-1,2)]:
    pivot=world([1.0358+sign*.53,2.75,.70]);node('wing_'+side,'body_posture',pivot)
    fold=Matrix.Rotation(math.radians(sign*20),3,'Z');pitch=Matrix.Rotation(math.radians(-18),3,'X')
    wr=ROT@pitch@fold@ROT.inverted();W=np.array(wr)
    wingraw=raw[components==cid];wx=wingraw[:,0];wy=wingraw[:,1]
    design=np.column_stack((np.ones(len(wx)),wx,wy,wx*wx,wx*wy,wy*wy))
    surface=np.linalg.lstsq(design,wingraw[:,2],rcond=None)[0]
    def wingwarp(v,r,p=pivot,W=W,surface=surface):
        q=r.copy();x=q[:,0];y=q[:,1];mid=np.column_stack((np.ones(len(x)),x,y,x*x,x*y,y*y))@surface
        q[:,2]=mid+.20*(q[:,2]-mid)
        return (world(q)-p)@W.T+p
    subset('wing_'+side+'__wing','wing_'+side,fl==cid,'wing',.035,wingwarp)

# Major leg components are split by distance to the measured joint centreline.
# Each minor bristle is attached intact to its nearest major anatomical surface.
source_leg={
 'foreleg':[[1.92,1.70,.30],[1.53,2.55,-1.16],[2.88,1.10,-1.48],[3.19,.72,-3.08],[3.60,-.17,-3.49]],
}
leg_components={'foreleg_L':229,'foreleg_R':96,'middleleg_L':238,'middleleg_R':1,'hindleg_L':237,'hindleg_R':0}
segment_masks={}; source_paths={}

def closest_segment(p,points):
    d=[]
    for a,b in zip(points[:-1],points[1:]):
        ab=b-a;t=np.clip(((p-a)@ab)/(ab@ab),0,1);q=a+t[:,None]*ab;d.append(np.sum((p-q)**2,axis=1))
    return np.argmin(np.array(d),axis=0)

def solve(a,c,l1,l2,pole):
    axis=c-a;d=axis.length;axis.normalize();along=(l1*l1-l2*l2+d*d)/(2*d)
    pp=Vector(pole)-axis*Vector(pole).dot(axis);pp.normalize()
    return a+axis*along+pp*math.sqrt(max(0,l1*l1-along*along))

def leg_quats(src,dst):
    qs=[];prev=IDENT
    for i in range(4):
        # Parallel transport the previous segment's roll. Independent shortest
        # arcs can introduce a half-turn twist at an otherwise ordinary hinge.
        q=(prev@(src[i+1]-src[i])).rotation_difference(dst[i+1]-dst[i])@prev;qs.append(prev.inverted()@q);prev=q
    return qs

for side,sign in [('L',1),('R',-1)]:
    prefix='foreleg_'+side;rp=np.array(source_leg['foreleg']);rp[:,0]=1.0358+sign*(rp[:,0]-1.0358);pts=[Vector(p) for p in world(rp)];source_paths[prefix]=pts
    part=closest_segment(fc,rp);parent='body_posture'
    for j,kind in enumerate(['coxa','femur','tibia','tarsus']):
        name=prefix+'_'+kind;node(name,parent,pts[j]);parent=name
        segment_masks[name]=(fl==leg_components[prefix])&(part==j)
    # Retain a continuous source surface across each joint. The four exact
    # contract nodes become glTF skin joints, avoiding detached rigid cut edges.
    ob=subset(prefix+'__cuticle','body_posture',fl==leg_components[prefix],'leg',.36)
    ob['skin_prefix']=prefix
    lengths=[(pts[i+1]-pts[i]).length for i in range(4)]
    # Keep the coxa attached; solve the two long bones to a grounded tarsal wrist.
    rest=[p.copy() for p in pts];rest[3]=Vector((sign*.49,-.62,.13))
    footdir=Vector((sign*.10,-.36,-.93)).normalized();rest[4]=rest[3]+footdir*lengths[3]
    rest[3].z+=.01465-rest[4].z;rest[4].z=.01465
    rest[2]=solve(rest[1],rest[3],lengths[1],lengths[2],(sign,.2,.7))
    poses={'rest':rest,'feed':rest}
    for feeding in [False,True]:
        hrot=Matrix.Rotation(math.radians(30 if feeding else 0),3,'X')
        ac=origins['antenna_'+side]+Vector((0,-.045,-.055))
        ac=origins['head']+hrot@(ac-origins['head'])
        for label,stroke in [('A',-.022),('B',.022)]:
            p=[v.copy() for v in pts];p[1]=p[0]+Vector((sign*.55,-.70,-.35)).normalized()*lengths[0]
            target=ac+Vector((sign*.012,stroke,.008))
            direction=Vector((-sign*.32,.68,.65)).normalized()
            p[4]=target;p[3]=target-direction*lengths[3]
            p[2]=solve(p[1],p[3],lengths[1],lengths[2],(sign,0,0))
            poses[('both' if feeding else 'groom')+label]=p
    for k,pp in poses.items():
        qs=leg_quats(pts,pp)
        for j,kind in enumerate(['coxa','femur','tibia','tarsus']):
            name=prefix+'_'+kind;rig['joints'].setdefault(name,{})[k]=qjson(qs[j])
            if k=='rest':nodes[name].rotation_quaternion=qs[j]
    rig['legs'].append({'prefix':prefix,'sourcePoints':[vecjson(p) for p in pts],'restPoints':[vecjson(p) for p in rest],'lengths':lengths,'tipLocal':vecjson(pts[4]-pts[3]),'antennaLocal':vecjson(Vector((0,-.045,-.055)))})

# Static support legs retain connected topology; a smooth distal stance correction grounds each foot.
staticwarps={}
for prefix,cid in leg_components.items():
    if prefix.startswith('foreleg'):continue
    ids=np.flatnonzero(components==cid);p=verts[ids];lo=p[:,2].min();hi=p[:,2].max()
    def warp(v,r,lo=lo,hi=hi):
        v=v.copy();t=np.clip((hi-v[:,2])/(hi-lo),0,1);v[:,2]-=lo*t*t;return v
    staticwarps[cid]=warp;node(prefix,'body_posture');subset(prefix+'__cuticle',prefix,fl==cid,'leg',.26,warp)

# Associate all small components to the actual nearest surface, not their chunk index.
major=[120,146,86,147,0,237,1,238,96,229];kd=KDTree(sum(np.count_nonzero(components==i) for i in major))
idx=0
for i in np.flatnonzero(np.isin(components,major)):
    kd.insert(Vector(raw[i]),int(i));idx+=1
kd.balance();assign=defaultdict(list)
for cid in range(int(components.max()+1)):
    if cid in major or cid in [183,2,116,117,118]:continue
    ids=np.flatnonzero(components==cid);center=raw[ids].mean(0);_,near,_=kd.find(Vector(center));owner=int(components[near]);parent='body_posture';warp=None
    if owner==120 or owner in [86,147]:
        parent='head'
        if center[1]<-.85 and .4<center[2]<1.15:parent='antenna_'+('L' if center[0]>1.0358 else 'R')
    elif owner==146:parent='abdomen'
    else:
        prefix=next(k for k,v in leg_components.items() if v==owner)
        if prefix.startswith('foreleg'):
            rp=np.array(source_leg['foreleg']);sg=1 if prefix.endswith('L') else -1;rp[:,0]=1.0358+sg*(rp[:,0]-1.0358)
            j=int(closest_segment(center[None,:],rp)[0]);parent=prefix+'_'+['coxa','femur','tibia','tarsus'][j]
        else:parent=prefix
    assign[(parent,owner)].append(cid)
# Remove the scan's broad spike-like cross-sections while retaining each curved centreline.
for cid in [i for ids in assign.values() for i in ids]:
    ids=np.flatnonzero(components==cid);v=verts[ids];center=v.mean(0)
    _,_,axes=np.linalg.svd(v-center,full_matrices=False);t=(v-center)@axes[0]
    if np.ptp(t)>1e-8:
        centerline=np.column_stack([np.polyval(np.polyfit(t,v[:,k],3),t) for k in range(3)])
        verts[ids]=centerline+.34*(v-centerline)
for (parent,owner),ids in assign.items():
    # Thin existing large conical bristles along their principal axis, retaining their curves.
    def hairwarp(v,r,owner=owner):return staticwarps[owner](v,r) if owner in staticwarps else v
    if parent.startswith('foreleg'):
        prefix='_'.join(parent.split('_')[:2]);ob=subset(parent+'__source_hair','body_posture',np.isin(fl,ids),'hair',.12,hairwarp);ob['skin_prefix']=prefix
    else:subset(parent+'__source_hair',parent,np.isin(fl,ids),'hair',.12,hairwarp)

# Small dark sockets sit at the actual source macrochaeta roots. Their pigment
# is added to the existing colour attribute, never an unrelated photo texture.
for parent,owner in [('abdomen',146),('head',120)]:
    surface=next(o for o in meshes if o.name==('thorax_abdomen__cuticle' if parent=='abdomen' else 'head__cuticle'))
    vv=np.array([v.co[:] for v in surface.data.vertices])+np.array(origins[parent]);shade=np.ones(len(vv))
    for (p,o),ids in assign.items():
        if p!=parent:continue
        for cid in ids:
            points=raw[components==cid];nearest=[kd.find(Vector(x)) for x in points[::max(1,len(points)//32)]]
            root,_,distance=min(nearest,key=lambda x:x[2])
            if distance>.35:continue
            d2=np.sum((vv-world(root))**2,axis=1);shade*=1-.58*np.exp(-d2/(.012**2))
    attr=surface.data.color_attributes['Color'];cc=np.empty((len(vv),4),dtype=np.float32);attr.data.foreach_get('color',cc.ravel());cc[:,:3]*=shade[:,None];attr.data.foreach_set('color',cc.ravel())

# Preserve the actual retracted mouth: original vertices, faces and amber/cream colours.
# These are small spatial cuts in component 120, not a newly modelled proboscis.
oral_ids=np.unique(faces[mouthmask]);oral_pivot=Vector(world([1.0358,-.18,-.18]))
node('proboscis_rostrum','head',oral_pivot)
node('proboscis_haustellum','proboscis_rostrum',world([1.0358,-.24,-.30]))
node('proboscis_labellum','proboscis_haustellum',world([1.0358,-.30,-.43]))
for side,sg in [('L',1),('R',-1)]:
    node('labellum_lobe_'+side,'proboscis_labellum',world([1.0358+sg*.10,-.30,-.43]))
subset('proboscis_rostrum__oral','proboscis_rostrum',mouthmask&(fc[:,2]>=-.30),'oral',.9)
subset('proboscis_haustellum__oral','proboscis_haustellum',mouthmask&(fc[:,2]<-.30)&(fc[:,2]>=-.43),'oral',.9)
for side,sg in [('L',1),('R',-1)]:
    subset('labellum_lobe_'+side+'__oral','labellum_lobe_'+side,mouthmask&(fc[:,2]<-.43)&((fc[:,0]-1.0358)*sg>=0),'oral',.95)
rig['mouthSource']={'component':120,'sourceTriangles':int(mouthmask.sum()),'sourceVertices':len(oral_ids),'method':'spatial cuts; original positions and COLOR_0; cut boundaries capped; no replacement stalk or pads'}

# Fine hairs are rooted on the actual simplified surface, with area-weighted deterministic sampling.
rng=np.random.default_rng(1739)
def tube(v,f,c,path,radii,color):
    base=len(v)
    for i,p in enumerate(path):
        direction=Vector(path[min(i+1,len(path)-1)])-Vector(path[max(0,i-1)]);direction.normalize()
        ref=Vector((1,0,0)) if abs(direction.x)<.9 else Vector((0,1,0));u=direction.cross(ref).normalized();w=direction.cross(u).normalized()
        for j in range(3):
            a=j*2*math.pi/3;v.append(tuple(Vector(p)+radii[i]*(u*math.cos(a)+w*math.sin(a))));c.append((*color,1))
    for i in range(len(path)-1):
        for j in range(3):a=base+i*3+j;b=base+i*3+(j+1)%3;f.extend([(a,b,b+3),(a,b+3,a+3)])
for ob in list(meshes):
    if not ob.name.endswith('__cuticle'):continue
    me=ob.data;me.calc_loop_triangles();vv=np.array([v.co[:] for v in me.vertices]);ff=np.array([p.vertices[:] for p in me.loop_triangles]);tri=vv[ff];cross=np.cross(tri[:,1]-tri[:,0],tri[:,2]-tri[:,0]);areas=np.linalg.norm(cross,axis=1)*.5
    count=int(areas.sum()*(1050 if ob.parent.name in ['abdomen','head'] else 750));count=min(count,1500)
    if not count:continue
    ids=rng.choice(len(ff),count,p=areas/areas.sum());hv=[];hf=[];hc=[]
    normals=np.array([v.normal[:] for v in me.vertices])
    for t in ids:
        uv=rng.random(2)
        if uv.sum()>1:uv=1-uv
        b=np.array([1-uv.sum(),uv[0],uv[1]]);p=b@tri[t];n=Vector(b@normals[ff[t]]).normalized()
        # Short, combed microtrichia; long source macrochaetae remain clearly distinct.
        length=rng.uniform(.011,.028);tangent=Vector((0,.6,-.12));d=(n*.7+tangent*.3).normalized();p=Vector(p)
        tube(hv,hf,hc,[p-n*.001,p+d*length*.55,p+d*length+Vector((0,.003,-.001))],[.0010,.00065,.00006],[.095,.053,.018])
    hair=create_mesh(ob.name.removesuffix('__cuticle')+'__micro',ob.parent.name,hv,hf,hc,'hair')
    if 'skin_prefix' in ob:hair['skin_prefix']=ob['skin_prefix']
# Feathered aristae arise from the segmented source antennal funiculi.
for side,sg in [('L',1),('R',-1)]:
    hv=[];hf=[];hc=[];parent='antenna_'+side;p=Vector((sg*.02,-.04,-.025));end=p+Vector((sg*.17,-.04,.14))
    tube(hv,hf,hc,[p,(p+end)*.5,end],[.003,.0018,.00015],[.08,.045,.016])
    for i in range(1,10):
        q=p.lerp(end,i/11)
        for dr in [-1,1]:
            e=q+Vector((sg*.025,dr*.043,.036))*(1-i/14)
            tube(hv,hf,hc,[q,e],[.0011,.00006],[.09,.05,.019])
    create_mesh(parent+'__arista',parent,hv,hf,hc,'hair')

# Feeding bows the head and slightly lowers/spreads its own retracted mouth.
# A shallow nectar cap meets the source tissue; there is no lengthened shaft.
headfeed=Quaternion((1,0,0),math.radians(30));head=origins['head']
oral_shift=headfeed.inverted()@Vector((0,0,-.018))
for name,feed in [('head',headfeed),('antenna_L',IDENT),('antenna_R',IDENT),
                  ('proboscis_rostrum',Quaternion((1,0,0),math.radians(-5))),
                  ('proboscis_haustellum',IDENT),('proboscis_labellum',IDENT)]:
    rig['joints'][name]={'rest':qjson(IDENT),'feed':qjson(feed)}
rig['mouth']={'headPitch':30,'translation':vecjson(oral_shift),'spread':.0035,'tableY':0}
rig['antennae']={s:{'centerLocal':vecjson(Vector((0,-.045,-.055)))} for s in ['L','R']}
# Measure the actual source contact after the feed transform. The drop's crown
# lies at that contact, its flattened meniscus rests on the table.
q=Quaternion((1,0,0),math.radians(-5))
oralworld=np.array([head+headfeed@(oral_pivot+q@(Vector(p)-oral_pivot)+oral_shift-head) for p in verts[oral_ids]])
low=oralworld[:,2].min();contact=oralworld[oralworld[:,2]<low+.008].mean(0);contact[0]=0;contact[2]=low+.002
rig['mouth']['feedTip']=vecjson(contact)
rig['mouth']['nectar']={'position':vecjson(Vector((contact[0],contact[1],0))),'radius':.155,'height':float(contact[2]),'contactTolerance':.015}
# glTF-friendly smooth normals, original colour attribute only, no redundant UVs.
for ob in meshes:
    me=ob.data
    if len(me.polygons):
        mod=ob.modifiers.new('Triangles','TRIANGULATE');bpy.context.view_layer.objects.active=ob;bpy.ops.object.modifier_apply(modifier=mod.name)
# Blend neighbouring bones over 45 microns. Source positions remain intact in
# the GLB; inverse bind matrices express the measured original joint locations.
def skin_weights(v,prefix):
    pts=np.array(source_paths[prefix]);d=[]
    for a,b in zip(pts[:-1],pts[1:]):
        ab=b-a;t=np.clip(((v-a)@ab)/(ab@ab),0,1);q=a+t[:,None]*ab;d.append(np.sum((v-q)**2,axis=1))
    w=1/(np.array(d).T+.045**2)**4;w/=w.sum(1)[:,None]
    return w
skin_cache={}
def world_vertices(ob):
    v=np.array([q.co[:] for q in ob.data.vertices])
    if 'skin_prefix' not in ob:return np.array([ob.matrix_world@Vector(p) for p in v])
    prefix=ob['skin_prefix'];weights=skin_cache.setdefault(ob.name,skin_weights(v,prefix));result=np.zeros_like(v)
    for i,part in enumerate(['coxa','femur','tibia','tarsus']):
        name=prefix+'_'+part;m=np.array(nodes[name].matrix_world);rel=v-np.array(origins[name]);result+=(rel@m[:3,:3].T+m[:3,3])*weights[:,i,None]
    return result

# Camera support envelope is sampled from the actual geometry across all end poses.
direction=Vector((math.sin(math.radians(55))*math.cos(math.radians(15)), -math.cos(math.radians(55))*math.cos(math.radians(15)), math.sin(math.radians(15))))
target=Vector((0,0,.50));right=Vector((0,0,1)).cross(direction).normalized();up=direction.cross(right).normalized()
points=[]
for pose in ['rest','feed','groomA','groomB','bothA','bothB']:
    for name,j in rig['joints'].items():
        arr=j.get(pose,j['feed'] if pose.startswith('both') else j['rest']);nodes[name].rotation_quaternion=Quaternion((arr[3],arr[0],-arr[2],arr[1]))
    nodes['proboscis_rostrum'].location=oral_pivot-head+(oral_shift if pose in ['feed','bothA','bothB'] else Vector())
    bpy.context.view_layer.update()
    for ob in meshes:
        v=world_vertices(ob)-np.array(target);projected=np.column_stack((v@np.array(right),v@np.array(up),v@np.array(direction)))
        # Tight directional support points, not the eight loose corners of a 3D box.
        for angle in np.linspace(0,2*math.pi,32,endpoint=False):
            for depth in [-.2,0,.2]:points.append(projected[np.argmax(projected@np.array([math.cos(angle),math.sin(angle),depth]))].tolist())
points=np.unique(np.round(points,7),axis=0).tolist()
rig['camera']={'fov':20,'direction':vecjson(direction),'target':vecjson(target),'position':vecjson(target+direction*8),'wideWidthFraction':.64,'narrowWidthFraction':.86,'heightFraction':.83,'framingPoints':points}
# Restore the exact exported rest pose.
for name,j in rig['joints'].items():a=j['rest'];nodes[name].rotation_quaternion=Quaternion((a[3],a[0],-a[2],a[1]))
nodes['proboscis_rostrum'].location=oral_pivot-head
bpy.context.view_layer.update()
rig['footContacts']=[]
for prefix in leg_components:
    name=prefix+'__cuticle'
    ob=next(o for o in meshes if o.name==name);v=world_vertices(ob);low=v[:,2].min()
    tip=v[v[:,2]<low+.004].mean(0);tip[2]=0
    rig['footContacts'].append({'front':prefix.startswith('foreleg'),'position':vecjson(tip)})
bpy.ops.object.select_all(action='DESELECT')
for ob in list(nodes.values())+meshes:ob.select_set(True)
bpy.ops.export_scene.gltf(filepath=str(HERE/'fly.glb'),export_format='GLB',use_selection=True,export_animations=False,export_yup=True,export_extras=True,export_texcoords=False,export_normals=True,export_materials='EXPORT',export_attributes=False)
# Add standard glTF skins to the existing named joint hierarchy. Blender empties
# export unchanged, then GLTFLoader recognizes the listed nodes as bones. This
# avoids an extra armature parent and preserves the public articulation contract.
glb=(HERE/'fly.glb').read_bytes();json_length=struct.unpack_from('<I',glb,12)[0]
doc=json.loads(glb[20:20+json_length]);binary=bytearray(glb[28+json_length:]);doc['skins']=[]
def accessor(data,component_type,kind,target=None):
    while len(binary)%4:binary.append(0)
    offset=len(binary);payload=data.tobytes();binary.extend(payload)
    view={'buffer':0,'byteOffset':offset,'byteLength':len(payload)}
    if target:view['target']=target
    doc['bufferViews'].append(view);doc['accessors'].append({'bufferView':len(doc['bufferViews'])-1,'componentType':component_type,'count':len(data),'type':kind})
    return len(doc['accessors'])-1
def read_positions(index):
    a=doc['accessors'][index];bv=doc['bufferViews'][a['bufferView']]
    return np.ndarray((a['count'],3),dtype='<f4',buffer=binary,offset=bv.get('byteOffset',0)+a.get('byteOffset',0),strides=(bv.get('byteStride',12),4)).copy()
node_ids={n['name']:i for i,n in enumerate(doc['nodes'])}
for prefix in source_paths:
    names=[prefix+'_'+p for p in ['coxa','femur','tibia','tarsus']];inverses=[]
    for name in names:
        m=np.eye(4,dtype='<f4');m[:3,3]=-np.array(vecjson(origins[name]));inverses.append(m.T.flatten())
    doc['skins'].append({'name':prefix+'_skin','inverseBindMatrices':accessor(np.array(inverses,dtype='<f4'),5126,'MAT4'),'joints':[node_ids[n] for n in names],'skeleton':node_ids[names[0]]})
    for n in doc['nodes']:
        if n.get('extras',{}).get('skin_prefix')!=prefix:continue
        n['skin']=len(doc['skins'])-1
        for primitive in doc['meshes'][n['mesh']]['primitives']:
            p=read_positions(primitive['attributes']['POSITION']);blenderp=p[:,[0,2,1]].copy();blenderp[:,1]*=-1
            weights=skin_weights(blenderp,prefix).astype('<f4');joints=np.tile(np.arange(4,dtype='u1'),(len(p),1))
            primitive['attributes']['JOINTS_0']=accessor(joints,5121,'VEC4',34962)
            primitive['attributes']['WEIGHTS_0']=accessor(weights,5126,'VEC4',34962)
# glTF skins use scene-root mesh nodes. Their named bones remain under fly_root,
# so moving fly_root still moves every skinned vertex through its joint matrix.
# Keeping a skinned mesh below a transformed parent would be ambiguous in glTF.
skin_nodes=[i for i,n in enumerate(doc['nodes']) if 'skin' in n]
for n in doc['nodes']:
    if 'children' in n:n['children']=[i for i in n['children'] if i not in skin_nodes]
    if n.get('children')==[]:n.pop('children',None)
doc['scenes'][doc.get('scene',0)]['nodes'].extend(skin_nodes)
doc['buffers'][0]['byteLength']=len(binary)
json_bytes=json.dumps(doc,separators=(',',':')).encode();json_bytes+=b' '*((-len(json_bytes))%4);binary.extend(b'\0'*((-len(binary))%4))
(HERE/'fly.glb').write_bytes(struct.pack('<III',0x46546c67,2,28+len(json_bytes)+len(binary))+struct.pack('<II',len(json_bytes),0x4e4f534a)+json_bytes+struct.pack('<II',len(binary),0x004e4942)+binary)
triangles=sum(len(ob.data.polygons) for ob in meshes);size=(HERE/'fly.glb').stat().st_size
stats={'sourceTriangles':source_triangles,'cleanedSourceTriangles':len(faces),'weldedSourceVertices':len(raw),'sourceComponents':int(components.max()+1),'triangles':triangles,'glbBytes':size,'meshes':len(meshes),'sourceSha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'builder':'build_scan.py','bodyLengthMM':2.5}
(HERE/'build_stats.json').write_text(json.dumps(stats,indent=2)+'\n');(HERE/'rig.json').write_text(json.dumps(rig,separators=(',',':'))+'\n')
print(json.dumps(stats),flush=True);assert triangles<=200000,triangles;assert size<=8000000,size
# Segmentation plates use the same exported geometry, coloured per articulation parent.
if '--no-render' not in sys.argv:
    for i,ob in enumerate(meshes):
        if 'skin_prefix' in ob:
            v=world_vertices(ob)
            for vert,p in zip(ob.data.vertices,v):vert.co=p
            ob.data.update()
        m=bpy.data.materials.new('diagnostic_'+ob.parent.name);m.diffuse_color=(*[.22+.65*x for x in np.random.default_rng(sum(map(ord,ob.parent.name))).random(3)],1);ob.data.materials.clear();ob.data.materials.append(m)
    scene.render.engine='BLENDER_WORKBENCH';scene.display.shading.light='STUDIO';scene.display.shading.color_type='MATERIAL';scene.display.shading.show_shadows=True;scene.display.shading.show_cavity=True;scene.display.shading.background_type='WORLD';scene.world.color=(.045,.045,.045)
    scene.render.resolution_x=1400;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    bpy.ops.object.camera_add();cam=bpy.context.object;scene.camera=cam;cam.data.type='ORTHO';cam.data.ortho_scale=6.0
    allv=np.concatenate([np.array([ob.matrix_world@v.co for v in ob.data.vertices]) for ob in meshes]);diagtarget=Vector((allv.min(0)+allv.max(0))/2)
    for label,loc in [('side',(7,0,.5)),('front',(0,-7,.6)),('top',(0,0,7))]:
        cam.location=Vector(loc)+diagtarget;cam.rotation_euler=(diagtarget-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(HERE/'renders'/('segments_'+label+'.png'));bpy.ops.render.render(write_still=True)
