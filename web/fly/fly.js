/* Fly Séance — scan specimen controller, MIT; model credit in MODEL-LICENSE.txt. No CDN or build step. */
import * as THREE from 'three';
import { GLTFLoader } from '../vendor/addons/loaders/GLTFLoader.js';
import { applySpecimenMaterials } from './materials.js';
import { RoomEnvironment } from '../vendor/addons/environments/RoomEnvironment.js';

const DEG = Math.PI / 180;
const clampDrive = value => Number.isFinite(value) ? Math.max(0, Math.min(1, value)) : 0;

// Exact critically damped integration for a constant target over this frame.
function spring(state, target, dt) {
  const omega = 11, displacement = state.value - target;
  const term = state.velocity + omega * displacement, decay = Math.exp(-omega * dt);
  state.value = target + (displacement + term * dt) * decay;
  state.velocity = (state.velocity - omega * term * dt) * decay;
  if (Math.abs(state.value - target) < .00001 && Math.abs(state.velocity) < .0001) {
    state.value = target; state.velocity = 0;
  }
}

// Original procedural walnut grain. Created once, never during animation.
function woodTexture() {
  const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 512;
  const context = canvas.getContext('2d'), image = context.createImageData(512, 512);
  let seed = 8231;
  for (let y = 0; y < 512; y++) for (let x = 0; x < 512; x++) {
    seed = (Math.imul(seed, 1664525) + 1013904223) | 0;
    const noise = (seed >>> 0) / 4294967296;
    const bend = 6 * Math.sin(x * .012) + 2 * Math.sin(x * .038 + y * .006);
    const grain = Math.sin((y + bend) * .64) * .5 + Math.sin((y + bend) * 2.19) * .23;
    const darkPore = Math.pow(Math.max(0, Math.sin(y * 1.4 + bend * .24)), 18) * 4;
    const v = 28 + grain * 1.3 + noise * 1.4 - darkPore * .18;
    const i = (y * 512 + x) * 4;
    image.data[i] = v * 1.16; image.data[i + 1] = v * .78; image.data[i + 2] = v * .49;
    // Fade only the distant boundary of the table, leaving transparent background.
    const edge = Math.max(Math.abs(x - 255.5), Math.abs(y - 255.5)) / 255.5;
    image.data[i + 3] = Math.round(255 * Math.min(1, (1 - edge) * 7));
  }
  context.putImageData(image, 0, 0);
  const texture = new THREE.CanvasTexture(canvas); texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 4;
  return texture;
}

function contactTexture() {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 128;
  const c = canvas.getContext('2d'), gradient = c.createRadialGradient(64,64,4,64,64,64);
  gradient.addColorStop(0,'rgba(0,0,0,.55)'); gradient.addColorStop(.4,'rgba(0,0,0,.31)');
  gradient.addColorStop(1,'rgba(0,0,0,0)'); c.fillStyle=gradient; c.fillRect(0,0,128,128);
  return new THREE.CanvasTexture(canvas);
}

/**
 * Create a fly on a supplied canvas. Coordinates and geometry are in millimetres.
 * setDrive({feed,groom}) accepts independent continuous normalized firing rates.
 * setReducedMotion(boolean) is available for an in-page accessibility override.
 */
export async function createFly(canvas, options = {}) {
  if (!(canvas instanceof HTMLCanvasElement)) throw new TypeError('createFly needs a canvas element');
  const response = await fetch(new URL('./rig.json', import.meta.url));
  if (!response.ok) throw new Error(`Fly rig: HTTP ${response.status}`);
  const rig = await response.json();
  const gltf = await new GLTFLoader().loadAsync(new URL('./fly.glb', import.meta.url).href);
  const specimenMaterials=applySpecimenMaterials(gltf.scene);
  const geometries = new Set(), materials = new Set(), skeletons = new Set(), nodes = new Map();
  gltf.scene.traverse(object => {
    nodes.set(object.name, object);
    if (object.isMesh) {
      if(object.isSkinnedMesh)skeletons.add(object.skeleton);
      geometries.add(object.geometry);
      const list = Array.isArray(object.material) ? object.material : [object.material];
      for (const material of list) {
        materials.add(material);
        if (material.transparent) material.depthWrite = false;
      }
      object.castShadow = !list.some(material => material.transparent);
      const fineHair=/__micro|__source_hair|__arista/.test(object.name);
      if(fineHair)object.castShadow=false;
      object.receiveShadow = !fineHair;
      if (list.some(material => material.transparent)) object.renderOrder = 1;
    }
  });
  const asset = { scene: gltf.scene, nodes,
    dispose() { specimenMaterials.dispose();for (const skeleton of skeletons)skeleton.dispose();for (const g of geometries) g.dispose(); for (const m of materials) m.dispose(); } };
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance' }); }
  catch (error) { asset.dispose(); throw error; }
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = .96;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  const scene = new THREE.Scene(); scene.add(asset.scene);
  const pmrem = new THREE.PMREMGenerator(renderer), room = new RoomEnvironment();
  const environment = pmrem.fromScene(room, .04);
  scene.environment = environment.texture; scene.environmentIntensity = .27;
  room.dispose(); pmrem.dispose();
  const camera = new THREE.PerspectiveCamera(rig.camera.fov, 1, .02, 70);
  const target = new THREE.Vector3().fromArray(rig.camera.target);
  const cameraDirection = new THREE.Vector3().fromArray(rig.camera.direction);
  const halfFovTangent = Math.tan(rig.camera.fov * DEG / 2);
  camera.position.fromArray(rig.camera.position); camera.lookAt(target);
  // Four broad key samples emulate the luminous area of a nearby shaded candle
  // softbox; a cool rear source separates microtrichia and clear wing edges.
  // A neutral study mode is confined to the test canvas; the public API is unchanged.
  const neutral=canvas.dataset.lighting==='neutral';
  const candle = new THREE.SpotLight(neutral?0xffffff:0xffeee1,48,0,.85,.8,2);
  candle.position.set(-3.0,4.5,3.8);candle.target.position.set(0,.5,0);scene.add(candle.target);
  candle.castShadow = true;candle.shadow.mapSize.set(1024,1024);
  candle.shadow.camera.near = .1;candle.shadow.camera.far = 18;
  candle.shadow.bias = -.0004;candle.shadow.normalBias = .004;candle.shadow.radius = 4;
  scene.add(candle);
  for(const position of [[-4,4,3],[-2,5,3],[-3,4,5]]){
    const key=new THREE.PointLight(neutral?0xffffff:0xffeee1,14,0,2);key.position.fromArray(position);scene.add(key);
  }
  const rim=new THREE.DirectionalLight(neutral?0xffffff:0xd3dfee,1.15);rim.position.set(2.5,3,-3);scene.add(rim);
  scene.add(new THREE.HemisphereLight(neutral?0xffffff:0xd0d4dd,neutral?0x383838:0x433b31,.37));
  const wood = woodTexture(); wood.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
  const tableMaterial = new THREE.MeshStandardMaterial({ map: wood, roughness: .82,
    // Alpha coverage keeps the distant fade, while placing the receiver before
    // the transmission pass.
    metalness: 0, alphaToCoverage: true, depthWrite: true });
  const tableGeometry = new THREE.PlaneGeometry(18,18);
  const table = new THREE.Mesh(tableGeometry, tableMaterial); table.rotation.x = -Math.PI / 2;
  table.position.y = -.004; table.receiveShadow = true; table.renderOrder = -2; scene.add(table);
  const contactMap = contactTexture(), contactGeometry = new THREE.PlaneGeometry(2.5,3.5);
  const contactMaterial = new THREE.MeshBasicMaterial({ map: contactMap, transparent: true,
    opacity: .53, depthWrite: false, toneMapped: false });
  const contact = new THREE.Mesh(contactGeometry,contactMaterial); contact.rotation.x = -Math.PI/2;
  contact.position.set(0,-.002,-.20); contact.renderOrder = -1; scene.add(contact);

  const footShadowGeometry=new THREE.PlaneGeometry(.13,.13),footShadows=[];
  for(const foot of rig.footContacts){
    const material=new THREE.MeshBasicMaterial({map:contactMap,transparent:true,opacity:.38,depthWrite:false,toneMapped:false});
    const mesh=new THREE.Mesh(footShadowGeometry,material);mesh.rotation.x=-Math.PI/2;
    mesh.position.fromArray(foot.position);mesh.position.y=-.0015;mesh.renderOrder=-1;scene.add(mesh);
    footShadows.push({material,front:foot.front});
  }
  const joints = Object.entries(rig.joints).map(([name,poses])=>{
    const node=asset.nodes.get(name);
    if(!node)throw new Error(`Missing articulated node: ${name}`);
    const q={};for(const [key,value] of Object.entries(poses))q[key]=new THREE.Quaternion().fromArray(value);
    return {name,node,q,target:new THREE.Quaternion(),both:new THREE.Quaternion()};
  });
  const lobeL=asset.nodes.get('labellum_lobe_L'),lobeR=asset.nodes.get('labellum_lobe_R');
  const rostrum=asset.nodes.get('proboscis_rostrum'),mouthRest=rostrum.position.clone();
  const mouthShift=new THREE.Vector3().fromArray(rig.mouth.translation);
  const lobeRestL=lobeL.position.clone(),lobeRestR=lobeR.position.clone();
  const MOUTH_REACH=5.5,MOUTH_DAB=.25,MOUTH_SPREAD=3,LOBE_PUMP=.006;
  // One shallow spherical cap on the table, not an attached mouth primitive.
  const mouthShadowGeometry=new THREE.PlaneGeometry(.34,.25);
  const mouthShadowMaterial=new THREE.MeshBasicMaterial({map:contactMap,transparent:true,opacity:0,depthWrite:false,toneMapped:false});
  const mouthShadow=new THREE.Mesh(mouthShadowGeometry,mouthShadowMaterial);mouthShadow.rotation.x=-Math.PI/2;
  mouthShadow.position.fromArray(rig.mouth.feedTip);mouthShadow.position.y=-.001;mouthShadow.renderOrder=-1;scene.add(mouthShadow);
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  let automaticMotionPreference = options.reducedMotion === undefined;
  let reduced = options.reducedMotion ?? media.matches;
  let desiredFeed = 0, desiredGroom = 0, disposed = false, raf = 0, previousTime = 0;
  let feedPhase = 0, groomPhase = 0;
  const feedSpring = { value: 0, velocity: 0 }, groomSpring = { value: 0, velocity: 0 };
  function pose(dt) {
    let f,g;
    if(reduced){
      f=desiredFeed>0&&desiredFeed>=desiredGroom?1:0;
      g=desiredGroom>desiredFeed?1:0;
      feedSpring.value=f;feedSpring.velocity=0;groomSpring.value=g;groomSpring.velocity=0;
    }else{
      spring(feedSpring,desiredFeed,dt);spring(groomSpring,desiredGroom,dt);
      f=feedSpring.value;g=groomSpring.value;
      feedPhase=(feedPhase+dt*Math.PI*2*(.42+1.15*f))%(Math.PI*2);
      groomPhase=(groomPhase+dt*Math.PI*2*(.32+1.85*g))%(Math.PI*2);
    }
    const wave=reduced?0:Math.sin(groomPhase),pump=reduced?0:Math.sin(feedPhase)*f;
    for(const foot of footShadows)foot.material.opacity=foot.front?.38*(1-g)*(1-g):.38;
    for(const j of joints){
      j.node.quaternion.slerpQuaternions(j.q.rest,j.q.feed,f);
      if(j.q.groomA){
        const blend=.5+.5*wave*(j.name.includes('_R')?-1:1);
        j.target.slerpQuaternions(j.q.groomA,j.q.groomB,blend);
        j.both.slerpQuaternions(j.q.bothA,j.q.bothB,blend);
        j.target.slerp(j.both,f);j.node.quaternion.slerp(j.target,g);
      }
      if(j.name.startsWith('antenna_')){
        const sign=j.name.endsWith('L')?1:-1;
        j.node.rotation.z=sign*.018*g*wave;
      }
    }
    // Actual source tissue stays at its original scale. The mouth reaches the
    // table (MOUTH_REACH times the rig's shift, about 0.1 mm) and dabs it in time
    // with the pump, so feeding reads at page size; the lobes open as it touches.
    const dab=Math.max(0,pump)*MOUTH_DAB;
    // While the forelegs groom, the mouth stays higher so the legs do not hide it.
    rostrum.position.copy(mouthRest).addScaledVector(mouthShift,f*MOUTH_REACH*(1-dab)*(1-.8*g));
    const spread=(rig.mouth.spread*MOUTH_SPREAD+LOBE_PUMP*(.5+.5*pump))*f;
    lobeL.position.copy(lobeRestL);lobeL.position.x+=spread;
    lobeR.position.copy(lobeRestR);lobeR.position.x-=spread;
    mouthShadowMaterial.opacity=.22*f;
  }
  function render(time) {
    raf = 0;
    if (disposed) return;
    const dt = previousTime ? Math.min((time - previousTime) / 1000, .05) : 1 / 60;
    previousTime = time;
    pose(dt);renderer.render(scene,camera);
    if (!reduced && !document.hidden) raf = requestAnimationFrame(render);
  }
  function schedule() {
    if (!disposed && !raf) raf = requestAnimationFrame(render);
  }
  function resize() {
    if (disposed) return;
    const width = Math.max(1,canvas.clientWidth), height = Math.max(1,canvas.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1,2));
    renderer.setSize(width,height,false);camera.aspect = width / height;
    // Fit the complete swept silhouette, including feeding and both grooming
    // strokes. Resize changes distance only, never the viewing direction.
    const mix=Math.min(1,Math.max(0,(camera.aspect-1.2)/(1280/520-1.2)));
    const fraction=rig.camera.narrowWidthFraction+(rig.camera.wideWidthFraction-rig.camera.narrowWidthFraction)*mix;
    const points=rig.camera.framingPoints;
    let near=0;
    for(let i=0;i<points.length;i++)near=Math.max(near,points[i][2]+.1);
    let far=30,minX=0,maxX=0,minY=0,maxY=0;
    for(let step=0;step<41;step++){
      const distance=step===40?far:(near+far)*.5;
      minX=Infinity;maxX=-Infinity;minY=Infinity;maxY=-Infinity;
      for(let i=0;i<points.length;i++){
        const p=points[i],den=(distance-p[2])*halfFovTangent;
        const x=p[0]/(den*camera.aspect),y=p[1]/den;
        minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
      }
      if(step<40){
        if((maxX-minX)*.5>fraction||(maxY-minY)*.5>rig.camera.heightFraction)near=distance;
        else far=distance;
      }
    }
    camera.position.copy(cameraDirection).multiplyScalar(far).add(target);
    // Lens shift centers the swept bounds without tilting the camera or
    // stretching the image. This uses the full height of a wide stage.
    camera.setViewOffset(width,height,(minX+maxX)*width/4,-(minY+maxY)*height/4,width,height);
    camera.updateProjectionMatrix(); schedule();
  }
  function onVisibility() {
    previousTime = 0;
    if (document.hidden) { cancelAnimationFrame(raf); raf = 0; }
    else schedule();
  }
  function changeMotion(value) {
    reduced = !!value; previousTime = 0;
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    schedule();
  }
  function onPreference(event) { if (automaticMotionPreference) changeMotion(event.matches); }
  const observer = new ResizeObserver(resize); observer.observe(canvas);
  media.addEventListener('change',onPreference);
  document.addEventListener('visibilitychange',onVisibility);
  resize();
  return {
    setDrive(drive = {}) {
      if (disposed) return;
      desiredFeed = clampDrive(drive.feed); desiredGroom = clampDrive(drive.groom); schedule();
    },
    setReducedMotion(value) { if (!disposed) { automaticMotionPreference = false; changeMotion(value); } },
    dispose() {
      if (disposed) return; disposed = true; cancelAnimationFrame(raf); observer.disconnect();
      document.removeEventListener('visibilitychange',onVisibility); media.removeEventListener('change',onPreference);
      asset.dispose(); environment.dispose(); wood.dispose(); contactMap.dispose(); tableGeometry.dispose(); tableMaterial.dispose();
      contactGeometry.dispose(); contactMaterial.dispose();footShadowGeometry.dispose();for(const foot of footShadows)foot.material.dispose();mouthShadowGeometry.dispose(); mouthShadowMaterial.dispose(); candle.shadow.map?.dispose();
      renderer.dispose(); renderer.forceContextLoss();
    },
  };
}
