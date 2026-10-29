// Offline integration/geometry checks. Uses only the preinstalled browser tooling.
import {readFile,writeFile,mkdir,rm} from 'node:fs/promises';
import {dirname,resolve,extname,join} from 'node:path';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
import {chromium,webkit} from '/opt/homebrew/lib/node_modules/@playwright/test/index.mjs';
import validator from '/opt/homebrew/lib/node_modules/@gltf-transform/cli/node_modules/gltf-validator/index.js';
const HERE=dirname(fileURLToPath(import.meta.url)),WEB=resolve(HERE,'..'),TEMP=join(HERE,'.browser-check');
await mkdir(TEMP,{recursive:true});process.env.TMPDIR=TEMP;
const raw=await readFile(join(HERE,'fly.glb')),gltf=JSON.parse(raw.subarray(20,20+raw.readUInt32LE(12)));
const rig=JSON.parse(await readFile(join(HERE,'rig.json'))),stats=JSON.parse(await readFile(join(HERE,'build_stats.json')));
const report={triangles:gltf.meshes.reduce((s,m)=>s+m.primitives.reduce((n,p)=>n+gltf.accessors[p.indices].count/3,0),0),glbBytes:raw.length,sourceComponents:stats.sourceComponents,browsers:{},failures:[]};
function check(value,message){if(!value)report.failures.push(message);}
check(report.triangles<=200000&&raw.length<=8000000,'Geometry exceeds web budget');
const names=new Map(gltf.nodes.map((n,i)=>[n.name,i])),parents=new Map();gltf.nodes.forEach((n,i)=>(n.children||[]).forEach(c=>parents.set(c,i)));
check(names.size===gltf.nodes.length,'Unique node names');
const chains=[['fly_root','body_posture','head','proboscis_rostrum','proboscis_haustellum','proboscis_labellum'],['head','antenna_L'],['head','antenna_R'],...['L','R'].map(s=>['body_posture',...['coxa','femur','tibia','tarsus'].map(p=>`foreleg_${s}_${p}`)])];
check(gltf.skins?.length===2&&gltf.skins.every(s=>s.joints.length===4),'Two continuous four-joint foreleg skins');
for(const n of gltf.nodes)if(n.skin!==undefined){check(!parents.has(names.get(n.name)),'Skinned mesh is a glTF scene root');for(const p of gltf.meshes[n.mesh].primitives)check(p.attributes.JOINTS_0!==undefined&&p.attributes.WEIGHTS_0!==undefined,'Foreleg skin attributes');}
for(const chain of chains)for(let i=1;i<chain.length;i++)check(names.has(chain[i])&&parents.get(names.get(chain[i]))===names.get(chain[i-1]),'Hierarchy: '+chain[i]);
check(rig.mouthSource?.component===120&&rig.mouthSource.sourceTriangles>2000,'Mouth reuses the source head component');
check(!gltf.meshes.some(m=>/__fringe/.test(m.name)),'No synthetic oral pads or fringes');
check(!gltf.animations?.length,'No baked animation clips');check(!gltf.images?.length,'No external/photo textures');
for(const m of gltf.meshes)for(const p of m.primitives)check(p.attributes.COLOR_0!==undefined,'Preserved vertex colours: '+m.name);
const validation=await validator.validateBytes(new Uint8Array(raw),{uri:'fly.glb',maxIssues:30});report.validator=validation.issues;check(!validation.issues.numErrors,'glTF validator errors');
const MIME={'.html':'text/html','.js':'text/javascript','.json':'application/json','.glb':'model/gltf-binary'};
const html='<!doctype html><style>html,body{margin:0;background:#100e0c}canvas{display:block;width:100vw;height:100vh}</style><canvas></canvas><script type="importmap">{"imports":{"three":"/vendor/three.module.min.js"}}</script>';
for(const engine of ['chromium','webkit']){
 const errors=[],browser=await(engine==='webkit'?webkit:chromium).launch(engine==='webkit'?{}:{args:['--use-angle=metal','--enable-gpu','--ignore-gpu-blocklist']});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:520},deviceScaleFactor:1});
  page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());if(url.origin!=='http://fly.local'){errors.push('Network request: '+url.href);return route.abort();}
   if(url.pathname==='/fly/qa.html')return route.fulfill({status:200,body:html,contentType:'text/html'});
   const path=resolve(WEB,'.'+decodeURIComponent(url.pathname));if(!path.startsWith(WEB+'/'))return route.fulfill({status:403});
   try{return route.fulfill({status:200,body:await readFile(path),contentType:MIME[extname(path)]||'application/octet-stream'})}catch{return route.fulfill({status:404})}
  });
  await page.addInitScript(()=>{const raf=requestAnimationFrame;window.frameCount=0;window.requestAnimationFrame=cb=>raf(t=>{frameCount++;cb(t)})});
  await page.goto('http://fly.local/fly/qa.html');
  await page.evaluate(async()=>{
   const THREE=await import('three');window.THREE=THREE;window.rig=await(await fetch('/fly/rig.json')).json();
   const add=THREE.Scene.prototype.add;THREE.Scene.prototype.add=function(...objects){if(objects.some(o=>o.getObjectByName('fly_root'))){window.scene=this;this.onBeforeRender=(r,s,c)=>{window.camera=c;window.renderer=r}}return add.apply(this,objects)};
   window.fly=await(await import('/fly/fly.js')).createFly(document.querySelector('canvas'),{reducedMotion:false});THREE.Scene.prototype.add=add;
   window.pose=()=>Object.fromEntries(Object.keys(rig.joints).map(n=>[n,scene.getObjectByName(n).quaternion.toArray()]));
   window.occlusions=()=>{
    scene.updateMatrixWorld(true);const parts=[];
    scene.traverse(o=>{if(o.isSkinnedMesh&&o.userData.skin_prefix){o.skeleton.update();o.computeBoundingSphere();parts.push(o)}});
    const ray=new THREE.Raycaster(),a=scene.getObjectByName('proboscis_haustellum').getWorldPosition(new THREE.Vector3()),b=scene.getObjectByName('proboscis_labellum').getWorldPosition(new THREE.Vector3());let count=0;
    for(const t of [.25,.5,.75,1]){const p=a.clone().lerp(b,t),d=p.clone().sub(camera.position);ray.set(camera.position,d.clone().normalize());ray.far=d.length()-.02;if(ray.intersectObjects(parts,false).length)count++}
    return count;
   };
   window.measure=()=>{
    scene.updateMatrixWorld(true);scene.traverse(o=>{if(o.isSkinnedMesh)o.skeleton.update()});camera.updateMatrixWorld(true);const v=new THREE.Vector3();let minX=Infinity,maxX=-Infinity,minY=Infinity,maxY=-Infinity;
    const nodes={};scene.getObjectByName('fly_root').parent.traverse(o=>{
     if(!o.isMesh)return;let low=Infinity,high=-Infinity;const p=o.geometry.attributes.position;
     for(let i=0;i<p.count;i++){v.fromBufferAttribute(p,i);if(o.isSkinnedMesh)o.applyBoneTransform(i,v);v.applyMatrix4(o.matrixWorld);low=Math.min(low,v.y);high=Math.max(high,v.y);v.project(camera);minX=Math.min(minX,v.x);maxX=Math.max(maxX,v.x);minY=Math.min(minY,v.y);maxY=Math.max(maxY,v.y)}
     nodes[o.name]={low,high};
    });
    const contacts={},surfaceContacts={};
    for(const leg of rig.legs){
     const side=leg.prefix.slice(-1),t=scene.getObjectByName(leg.prefix+'_tarsus'),a=scene.getObjectByName('antenna_'+side);
     const tip=t.localToWorld(new THREE.Vector3().fromArray(leg.tipLocal)),ant=a.localToWorld(new THREE.Vector3().fromArray(leg.antennaLocal));
     contacts[side]=tip.distanceTo(ant);
     const mesh=scene.getObjectByName(leg.prefix+'__cuticle'),p=mesh.geometry.attributes.position,sourceTip=new THREE.Vector3().fromArray(leg.sourcePoints[4]),q=new THREE.Vector3();let nearest=Infinity;
     for(let i=0;i<p.count;i++){q.fromBufferAttribute(p,i);if(q.distanceTo(sourceTip)>.070)continue;mesh.applyBoneTransform(i,q);q.applyMatrix4(mesh.matrixWorld);nearest=Math.min(nearest,q.distanceTo(ant));}
     surfaceContacts[side]=nearest;
    }
    let low=Infinity,high=-Infinity,contactGap=Infinity,penetration=Infinity,oralVertices=0;
    const n=rig.mouth.nectar,sr=(n.radius*n.radius+n.height*n.height)/(2*n.height);
    const mouthScale=[];
    scene.getObjectByName('proboscis_rostrum').traverse(o=>{
     mouthScale.push(o.scale.toArray());if(!o.isMesh)return;const p=o.geometry.attributes.position;
     for(let i=0;i<p.count;i++){
      v.fromBufferAttribute(p,i);if(o.isSkinnedMesh)o.applyBoneTransform(i,v);v.applyMatrix4(o.matrixWorld);low=Math.min(low,v.y);high=Math.max(high,v.y);oralVertices++;
      const r2=(v.x-n.position[0])**2+(v.z-n.position[2])**2;
      if(r2<n.radius*n.radius){const surface=Math.sqrt(sr*sr-r2)-sr+n.height,delta=v.y-surface;contactGap=Math.min(contactGap,Math.abs(delta));penetration=Math.min(penetration,delta)}
     }
    });
    const antennae={};for(const side of ['L','R']){const a=scene.getObjectByName('antenna_'+side);antennae[side]={scale:a.scale.toArray(),angle:a.quaternion.angleTo(new THREE.Quaternion())};}
    const eyeIntersections={L:0,R:0};
    for(const side of ['L','R']){
     const eye=scene.getObjectByName('head_'+side+'__eye');eye.geometry.computeBoundingBox();const box=eye.geometry.boundingBox,center=box.getCenter(new THREE.Vector3()),q=new THREE.Vector3(),ep=eye.geometry.attributes.position,ei=eye.geometry.index,planes=[];
     for(let i=0;i<ei.count;i+=3){const a=new THREE.Vector3().fromBufferAttribute(ep,ei.getX(i)),b=new THREE.Vector3().fromBufferAttribute(ep,ei.getX(i+1)),c=new THREE.Vector3().fromBufferAttribute(ep,ei.getX(i+2)),plane=new THREE.Plane().setFromCoplanarPoints(a,b,c);if(plane.distanceToPoint(center)>0)plane.negate();planes.push(plane)}
     scene.getObjectByName('fly_root').parent.traverse(o=>{if(!o.isMesh||!o.userData.skin_prefix||!o.name.endsWith('__cuticle'))return;const p=o.geometry.attributes.position;for(let i=0;i<p.count;i++){q.fromBufferAttribute(p,i);if(o.isSkinnedMesh)o.applyBoneTransform(i,q);q.applyMatrix4(o.matrixWorld);eye.worldToLocal(q);if(box.containsPoint(q)&&planes.every(p=>p.distanceToPoint(q)<-.001))eyeIntersections[side]++;}});
    }
    return {bounds:{minX,maxX,minY,maxY,width:(maxX-minX)/2,height:(maxY-minY)/2},contacts,surfaceContacts,antennae,eyeIntersections,
     mouth:{low,high,thickness:high-low,contactGap,penetration,oralVertices,unitScale:mouthScale.every(a=>a.every(x=>Math.abs(x-1)<1e-6)),gape:scene.getObjectByName('labellum_lobe_L').position.x},
     nectar:{count:scene.children.filter(o=>o.name==='nectar_drop').length},nodes};
   };
  });
  const measurements={};
  const bounds=b=>check(b.minX>-.99&&b.maxX<.99&&b.minY>-.99&&b.maxY<.99,`${engine} framing: ${JSON.stringify(b)}`);
  await page.waitForTimeout(1000);
  const initial=await page.evaluate(()=>pose());
  for(const [name,q] of Object.entries(initial))check(q.every((v,i)=>Math.abs(v-rig.joints[name].rest[i])<.0001),`${engine} rest quaternion ${name}`);
  for(const [state,f,g] of [['rest',0,0],['feed',1,0],['groom',0,1],['both',1,1],['intermediate',.5,.5]]){
   await page.evaluate(([feed,groom])=>fly.setDrive({feed,groom}),[f,g]);await page.waitForTimeout(1400);
   measurements[state]=await page.evaluate(()=>measure());bounds(measurements[state].bounds);
   if(g===1)for(const [side,d] of Object.entries(measurements[state].contacts))check(d<.055,`${engine} ${state} ${side} antenna contact ${d}`);
   const m=measurements[state];
   if(f===1)check(m.mouth.contactGap<.015&&m.mouth.penetration>-.015,`${engine} ${state} own-mouth nectar contact ${JSON.stringify(m.mouth)}`);
   check(m.nectar.count===0,`${engine} ${state} no visible nectar drop`);
   check(m.mouth.unitScale,`${engine} ${state} original mouth scale`);
   for(const [side,a] of Object.entries(m.antennae))check(a.angle<.021&&a.scale.every(x=>x===1),`${engine} ${state} ${side} antenna keeps its size and shape`);
   if(g===1){
    for(const [side,d] of Object.entries(m.surfaceContacts))check(d<.055,`${engine} ${state} actual ${side} tarsal tissue misses antenna: ${d}`);
    check(Object.values(m.eyeIntersections).every(n=>n===0),`${engine} ${state} forelegs pass through an eye: ${JSON.stringify(m.eyeIntersections)}`);
    for(const [name,b] of Object.entries(m.nodes))if(/^foreleg.*__cuticle$/.test(name))check(b.low>0,`${engine} ${state} raised leg below table: ${name}: ${b.low}`);
   }
  }
  check(Math.hypot(...rig.mouth.translation)<=.019,'Source mouth moves down only slightly');
  check(rig.mouth.nectar.height<.13&&rig.mouth.nectar.height<rig.mouth.nectar.radius,'Shallow small nectar cap');
  check(measurements.rest.bounds.width>.50,`${engine} specimen too small`);
  await page.evaluate(()=>fly.setDrive({feed:1,groom:1}));await page.waitForTimeout(1200);
  let occlusions=0;const groomSweep=[];
  for(let i=0;i<12;i++){
   occlusions+=await page.evaluate(()=>window.occlusions());const m=await page.evaluate(()=>measure());groomSweep.push({contacts:m.contacts,surfaceContacts:m.surfaceContacts,eyeIntersections:m.eyeIntersections,forelegLow:Math.min(...Object.entries(m.nodes).filter(([n])=>/^foreleg.*__cuticle$/.test(n)).map(([,b])=>b.low))});
   check(Object.values(m.eyeIntersections).every(n=>n===0),`${engine} combined grooming sweep intersects eyes`);
   check(Object.values(m.surfaceContacts).every(d=>d<.055),`${engine} grooming sweep actual tarsal contact`);
   check(groomSweep.at(-1).forelegLow>0,`${engine} combined grooming sweep crosses table`);
   await page.waitForTimeout(55);
  }
  check(occlusions===0,`${engine} grooming legs obscure source mouth: ${occlusions}`);
  const staticNodes=Object.keys(measurements.rest.nodes).filter(n=>/middleleg|hindleg|thorax_abdomen|wing_/.test(n));
  for(const n of staticNodes)for(const state of ['feed','groom','both'])check(Math.abs(measurements[state].nodes[n].low-measurements.rest.nodes[n].low)<1e-6,`${engine} supporting anatomy moved ${n}`);
  const footHeights=Object.fromEntries(Object.entries(measurements.rest.nodes).filter(([n])=>/(middleleg|hindleg|foreleg).*__cuticle/.test(n)).map(([n,b])=>[n,b.low]));
  for(const [n,y] of Object.entries(footHeights))check(Math.abs(y)<.002,`${engine} planted foot ${n}: ${y}`);
  await page.evaluate(()=>fly.setDrive({feed:1,groom:0}));await page.waitForTimeout(1400);
  const pump=[];for(let i=0;i<8;i++){pump.push((await page.evaluate(()=>measure())).mouth);await page.waitForTimeout(85)}
  for(const m of pump)check(m.contactGap<.015&&m.penetration>-.015&&m.unitScale,`${engine} source tissue remains in nectar contact: ${JSON.stringify(m)}`);
  check(Math.max(...pump.map(m=>m.gape))-Math.min(...pump.map(m=>m.gape))>.0008,`${engine} subtle source-mouth spreading`);
  const materials=await page.evaluate(()=>{const out={};scene.getObjectByName('fly_root').parent.traverse(o=>{if(o.isMesh)out[o.material.name]={physical:!!o.material.isMeshPhysicalMaterial,roughness:o.material.roughness,transmission:o.material.transmission,iridescence:o.material.iridescence,transparent:o.material.transparent,vertexColors:o.material.vertexColors}});return out});
  check(await page.evaluate(()=>renderer.getClearAlpha()===0),'Transparent canvas clear');
  check(Object.values(materials).every(m=>m.physical&&m.vertexColors),`${engine} physical vertex-colour materials`);check(materials.eye.roughness>.85,`${engine} matte eyes`);check(materials.wing.transparent&&materials.wing.iridescence===1,`${engine} transparent iridescent wings`);
  await page.evaluate(()=>fly.setDrive({feed:0,groom:1}));await page.waitForTimeout(1400);const a=await page.evaluate(()=>pose());await page.waitForTimeout(160);const b=await page.evaluate(()=>pose());check(JSON.stringify(a)!==JSON.stringify(b),`${engine} grooming alternation`);
  const times=await page.evaluate(()=>new Promise(resolve=>{const t=[];let prev=0;function tick(now){if(prev)t.push(now-prev);prev=now;if(t.length===120)resolve(t.sort((a,b)=>a-b));else requestAnimationFrame(tick)}requestAnimationFrame(tick)}));
  await page.setViewportSize({width:390,height:420});
  for(const [state,feed,groom] of [['phoneRest',0,0],['phoneBoth',1,1]]){await page.evaluate(([feed,groom])=>fly.setDrive({feed,groom}),[feed,groom]);await page.waitForTimeout(1400);measurements[state]=await page.evaluate(()=>measure());bounds(measurements[state].bounds)}
  await page.evaluate(()=>{fly.setReducedMotion(true);fly.setDrive({feed:.2,groom:.8})});await page.waitForTimeout(200);const still=await page.evaluate(()=>({pose:pose(),frames:frameCount}));await page.waitForTimeout(300);check(JSON.stringify(still)===JSON.stringify(await page.evaluate(()=>({pose:pose(),frames:frameCount}))),`${engine} reduced motion stops recurring frames`);
  await page.evaluate(()=>{fly.setReducedMotion(false);fly.setDrive({feed:-2,groom:NaN})});await page.waitForTimeout(1400);const clamped=await page.evaluate(()=>pose());check(JSON.stringify(initial)===JSON.stringify(clamped),`${engine} invalid drives clamp to rest`);
  await page.evaluate(()=>fly.dispose());await page.waitForTimeout(150);const frames=await page.evaluate(()=>frameCount);await page.waitForTimeout(180);check(frames===await page.evaluate(()=>frameCount),`${engine} dispose stops frames`);
  check(errors.length===0,`${engine} console errors: ${errors.join(';')}`);
  report.browsers[engine]={medianFrameMS:times[60],p95FrameMS:times[114],materials,footHeights,pump,foregroundLegOcclusions:occlusions,groomSweep,measurements,consoleErrors:errors};
  console.log(engine,'median',times[60].toFixed(2),'ms, cumulative failures:',report.failures.length);
 }finally{await browser.close()}
}
await writeFile(join(HERE,'verification.json'),JSON.stringify(report,null,2)+'\n');await rm(TEMP,{recursive:true,force:true});
console.log(JSON.stringify({triangles:report.triangles,glbBytes:report.glbBytes,validatorErrors:report.validator.numErrors,failures:report.failures},null,2));
assert.equal(report.failures.length,0,'See verification.json');
