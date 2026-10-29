/* Scan shading and original microscopic detail. Model attribution: MODEL-LICENSE.txt. */
import * as THREE from 'three';
const noise=`
varying vec3 vFlyPosition;
float flyHash(vec3 p){p=fract(p*.3183099+vec3(.11,.27,.43));p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float flyNoise(vec3 x){vec3 p=floor(x),f=fract(x);f=f*f*(3.-2.*f);return mix(mix(mix(flyHash(p),flyHash(p+vec3(1,0,0)),f.x),mix(flyHash(p+vec3(0,1,0)),flyHash(p+vec3(1,1,0)),f.x),f.y),mix(mix(flyHash(p+vec3(0,0,1)),flyHash(p+vec3(1,0,1)),f.x),mix(flyHash(p+vec3(0,1,1)),flyHash(p+vec3(1,1,1)),f.x),f.y),f.z);}
vec3 flyRelief(vec3 p,vec3 n,float h){vec3 dx=dFdx(p),dy=dFdy(p),r1=cross(dy,n),r2=cross(n,dx);float det=dot(dx,r1);vec3 g=sign(det)*(dFdx(h)*r1+dFdy(h)*r2);return normalize(abs(det)*n-g);}
// Two offset triangular lattices form a hexagonal ommatidial field. The cell
// relief fades below pixel resolution so distant eyes do not develop moire.
vec3 flyFacet(vec2 p){vec2 s=vec2(1.,1.7320508),a=mod(p,s)-s*.5,b=mod(p-s*.5,s)-s*.5;vec2 g=dot(a,a)<dot(b,b)?a:b;float d=max(abs(g.x),dot(abs(g),vec2(.5,.8660254)));float aa=max(length(fwidth(p)),.001);float resolved=1.-smoothstep(.30,.85,aa);float edge=smoothstep(.44-aa*.4,.5+aa*.4,d);return vec3((1.-dot(g,g)*3.)*resolved,edge*resolved,flyHash(vec3(floor((p-g)*20.)/20.,0.)));}
`;
export function applySpecimenMaterials(root){
 const converted=new Map();
 root.traverse(o=>{
  if(!o.isMesh)return;
  const source=o.material,key=source.name;
  if(converted.has(source)){o.material=converted.get(source);return;}
  const m=new THREE.MeshPhysicalMaterial({name:key,vertexColors:true,roughness:.48,metalness:0,
   color:0xffffff,ior:1.42,specularIntensity:.40,clearcoat:.055,clearcoatRoughness:.38,
   sheen:.25,sheenRoughness:.75,sheenColor:new THREE.Color(.55,.32,.12)});
  const eye=key==='eye',wing=key==='wing',hair=key==='hair',oral=key==='oral',leg=key==='leg',ocellus=key==='ocellus';
  if(eye){m.roughness=.97;m.specularIntensity=.07;m.clearcoat=0;m.sheen=.18;m.sheenColor.setRGB(.16,.025,.018);m.sheenRoughness=1;}
  else if(hair){m.roughness=.64;m.sheen=.85;m.specularIntensity=.35;m.clearcoat=0;}
  else if(oral){m.color.setRGB(.45,.38,.36);m.roughness=.49;m.specularIntensity=.27;m.transmission=.12;m.thickness=.014;m.attenuationColor.setRGB(.92,.78,.49);m.attenuationDistance=.25;m.sheen=.12;m.clearcoat=0;}
  else if(wing){m.transparent=true;m.depthWrite=false;m.opacity=1;m.roughness=.25;m.iridescence=1;m.iridescenceIOR=1.36;m.iridescenceThicknessRange=[230,520];m.specularIntensity=.20;m.sheen=0;m.clearcoat=.025;m.side=THREE.DoubleSide;}
  else if(ocellus){m.roughness=.4;m.specularIntensity=.3;m.clearcoat=.03;m.sheen=0;}
  else{m.roughness=leg?.48:.44;m.specularIntensity=leg?.34:.46;m.clearcoat=leg?.035:.06;m.sheen=.2;m.sheenColor.setRGB(.29,.20,.11);m.transmission=leg?.10:.035;m.thickness=leg?.022:.045;m.attenuationColor.setRGB(.88,.76,.55);m.attenuationDistance=.4;}
  m.onBeforeCompile=s=>{
   s.vertexShader='varying vec3 vFlyPosition;\n'+s.vertexShader;
   s.vertexShader=s.vertexShader.replace('#include <begin_vertex>','#include <begin_vertex>\nvFlyPosition=position;');
   s.fragmentShader=noise+s.fragmentShader;
   if(wing){
    s.fragmentShader=s.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
     float vein=1.-smoothstep(.35,.70,vColor.g);
     diffuseColor.rgb=mix(vec3(.80,.85,.9),vec3(.15,.085,.034),vein);
     diffuseColor.a=mix(.10,.76,vein);
    `);
    s.fragmentShader=s.fragmentShader.replace('#include <opaque_fragment>',`
     float facing=clamp(abs(dot(normalize(vNormal),normalize(vViewPosition))),0.,1.);
     float path=2.*(330.+80.*sin(vFlyPosition.z*5.+vFlyPosition.x*9.)+50.*sin(vFlyPosition.z*14.))*sqrt(1.-.48*(1.-facing*facing));
     vec3 film=.5+.5*cos(6.2831853*path/vec3(650.,510.,440.));
     outgoingLight=mix(vec3(.12,.15,.17)+film*.13,vec3(.07,.038,.014),vein)+totalSpecular*.10;
     #include <opaque_fragment>`);
   }else if(!hair){
    s.fragmentShader=s.fragmentShader.replace('#include <color_fragment>',`#include <color_fragment>
     diffuseColor.rgb*=.94+.12*flyNoise(vFlyPosition*32.);
     ${eye?`vec3 facet=flyFacet(vFlyPosition.zy*72.);diffuseColor.rgb*=(.94+.12*facet.z)*(1.-.16*facet.y);
     float pupil=smoothstep(.965,.9995,dot(normalize(vNormal),normalize(vViewPosition)));diffuseColor.rgb*=1.-.32*pupil;`:''}
    `);
    s.fragmentShader=s.fragmentShader.replace('#include <normal_fragment_maps>',`#include <normal_fragment_maps>
     float relief=${eye?'flyFacet(vFlyPosition.zy*72.).x*.00045':'flyNoise(vFlyPosition*190.)*.00020'};

     normal=flyRelief(-vViewPosition,normal,relief);
    `);
    if(!eye)s.fragmentShader=s.fragmentShader.replace('#include <roughnessmap_fragment>',`#include <roughnessmap_fragment>
     roughnessFactor=clamp(roughnessFactor+.18*(flyNoise(vFlyPosition*160.)-.5),.28,.8);`);
   }
  };
  m.customProgramCacheKey=()=> 'scan-pigment-v2-'+key;
  converted.set(source,m);o.material=m;
 });
 for(const m of converted.keys())m.dispose();
 return {dispose(){}};
}
