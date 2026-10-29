"""Read-only source inspection; writes only diagnostic images and component statistics."""
import bpy, numpy as np, json, pathlib, math, sys, os
from mathutils import Vector
HERE=pathlib.Path(__file__).resolve().parent
# The Sketchfab download (glTF), unzipped into data/ (not committed); FLY_SCAN overrides it.
SOURCE=pathlib.Path(os.environ.get('FLY_SCAN',HERE.parents[1]/'data/sketchfab-female/scene.gltf'))
def source_arrays():
    doc=json.loads(SOURCE.read_text()); blob=(SOURCE.parent/'scene.bin').read_bytes()
    def acc(i):
        a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']];dt={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}[a['componentType']];n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}[a['type']]
        out=np.ndarray((a['count'],n),dtype=dt,buffer=blob,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',n*np.dtype(dt).itemsize),np.dtype(dt).itemsize)).copy()
        if a.get('normalized'):out=out.astype(np.float32)/np.iinfo(dt).max
        return out
    vs=[];cs=[];fs=[];offset=0
    for m in doc['meshes']:
        p=m['primitives'][0];v=acc(p['attributes']['POSITION']);vs.append(v);cs.append(acc(p['attributes']['COLOR_0']));fs.append(acc(p['indices']).reshape(-1,3)+offset);offset+=len(v)
    v=np.concatenate(vs);c=np.concatenate(cs);f=np.concatenate(fs)
    _,inds,inv=np.unique(np.round(v,5),axis=0,return_index=True,return_inverse=True)
    v=v[inds];c=c[inds];f=inv[f]
    parent=np.arange(len(v))
    def find(a):
        while parent[a]!=a:parent[a]=parent[parent[a]];a=parent[a]
        return a
    for a,b,d in f:
        a=find(a);b=find(b);d=find(d);parent[b]=a;parent[d]=a
    labels=np.array([find(i) for i in range(len(v))]);_,labels=np.unique(labels,return_inverse=True)
    return v,c,f,labels
if __name__=='__main__':
    v,c,f,labels=source_arrays();print('RAW',v.min(0),v.max(0),len(v),len(f), 'components',labels.max()+1,flush=True)
    stats=[]
    for i in range(labels.max()+1):
        q=v[labels==i];col=c[labels==i];stats.append({'id':int(i),'n':len(q),'min':q.min(0).round(4).tolist(),'max':q.max(0).round(4).tolist(),'center':q.mean(0).round(4).tolist(),'color':col.mean(0).round(3).tolist()})
    stats.sort(key=lambda a:-a['n']);(HERE/'scan_components.json').write_text(json.dumps(stats,indent=2));print(json.dumps(stats[:45]),flush=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    
    if '--leg' in sys.argv:
        f=f[np.isin(labels[f[:,0]],[229])]
    if '--head' in sys.argv:
        f=f[np.all(v[f][:,:,1]<1.1,axis=1) & np.all(v[f][:,:,2]>-.65,axis=1)]
    mesh=bpy.data.meshes.new('source');mesh.from_pydata(v.tolist(),[],f.tolist());mesh.update();obj=bpy.data.objects.new('source',mesh);bpy.context.collection.objects.link(obj)
    ca=mesh.color_attributes.new(name='Color',type='FLOAT_COLOR',domain='POINT');ca.data.foreach_set('color',c.ravel())
    mat=bpy.data.materials.new('vertex');mat.use_nodes=True;nodes=mat.node_tree.nodes;attr=nodes.new('ShaderNodeVertexColor');attr.layer_name='Color';mat.node_tree.links.new(attr.outputs['Color'],nodes.get('Principled BSDF').inputs['Base Color']);nodes.get('Principled BSDF').inputs['Roughness'].default_value=.7;mesh.materials.append(mat)
    for p in mesh.polygons:p.use_smooth=True
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=12;scene.world.color=(.3,.3,.3);scene.render.resolution_x=1100;scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard'
    bpy.ops.object.light_add(type='AREA',location=(2,1,15));bpy.context.object.data.energy=1800;bpy.context.object.data.shape='DISK';bpy.context.object.data.size=10
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=14;scene.camera=cam
    views=[('top',(1,5,25)),('side',(23,5,0)),('front',(1,-20,0))]; target=(1,5,0); prefix='source_'
    if '--leg' in sys.argv:
        target=(2.5,1.25,-1.5);cam.data.ortho_scale=4.5;prefix='leg_';views=[('side',(23,1.25,-1.5)),('front',(2.5,-20,-1.5)),('top',(2.5,1.25,25))]
    if '--head' in sys.argv:
        target=(1,0,.7);cam.data.ortho_scale=3.3;prefix='head_';views=[('side',(23,0,.7)),('front',(1,-20,.7)),('top',(1,0,25))]
    for name,loc in views:
        cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();scene.render.filepath=str(HERE/'renders'/(prefix+name+'.png'));bpy.ops.render.render(write_still=True)
