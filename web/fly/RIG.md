This work is based on "Wildtype Female Drosophila Melanogaster"
(https://sketchfab.com/3d-models/wildtype-female-drosophila-melanogaster-3ba1adba62f34fe995413ee5e9cf3c25)
by mlykouretzos (https://sketchfab.com/mlykouretzos), licensed under CC-BY-4.0
(http://creativecommons.org/licenses/by/4.0/). Modified: decimated, segmented,
rigged, mouthparts articulated, materials changed. Rigging and code generated with
OpenAI Codex for Fly Séance.

# Fly articulation — source model edition

The specimen comes from mlykouretzos’s professionally modelled female Drosophila.
Its body, six legs, compound-eye surfaces, wing planforms, venation and major
bristles are retained. This is an anatomical sculpture with vertex colours,
not a photographic surface capture. The model is CC BY 4.0; rigging and browser
code use the project’s MIT licence. The current revision removes the earlier
extended-mouth reconstruction and restores the source mouth geometry.

## Rebuild and inspect

```sh
/Applications/Blender.app/Contents/MacOS/Blender --factory-startup -b -P web/fly/build_scan.py
node web/fly/verify.mjs
node web/fly/render_web.mjs
```

The builder reads `data/sketchfab-female/scene.gltf` and `scene.bin` (the glTF
download of the Sketchfab model, unzipped there; not committed; set `FLY_SCAN` to
read it from elsewhere) without modifying them. It uses Blender’s bundled NumPy and the
read-only decoder in `inspect_scan.py`. All output stays in `web/fly/`: `fly.glb`,
`rig.json`, `build_stats.json`, `MODEL-LICENSE.txt` and three segmentation plates.
Pass `-- --no-render` to skip the plates. No network, installation, external
texture service or runtime decoder is required. The earlier procedural builder (`build_fly.py`) is not part of the repository.

The source’s 15 arbitrary chunks become 503,816 welded vertices in 239 connected
components. Removing 132 duplicate/degenerate triangles precedes decimation.
Connected components identify body, eyes, wings and legs. Spatial cuts select
antennae and the actual retracted mouth from head component 120. Cut boundaries
are capped; no replacement stalk, pads, spheres or oral fringe are generated.
Folded internal eye triangles are replaced by a convex surface using the same
coloured outer vertices, fitted slightly outward to clear the face.

Per-part collapse decimation retains `COLOR_0`, with higher density on the eyes
and articulating face. The source mouth keeps its original amber/cream vertex
colours and positions. There are no embedded photographs or runtime image maps.
The photographs in comparison plates are QA references only.

The body retains its accepted 18° stance. Each wing folds 20° inward at its hinge,
cancels the body pitch, and has source thickness reduced around a fitted curved
mid-surface. Folded wing geometry, source veins and iridescent shading are
unchanged by the colour revision. Static support legs keep their grounded stance.
Original macrochaetae retain their curved centrelines with thinner cross-sections;
deterministic fine microtrichia and feathered aristae are batched geometry.

## Coordinates and API

```js
import { createFly } from './fly/fly.js';
const fly = await createFly(canvas, { reducedMotion: false });
fly.setDrive({ feed: 0.7, groom: 0.5 });
fly.setReducedMotion(true);
fly.dispose();
```

The API and séance-page integration are unchanged. Units are millimetres; body
length is about 2.5 mm. Blender uses +Z up, −Y anterior, +X anatomical left.
glTF/three.js uses +Y up, +Z anterior, +X left. The table is Y=0, with its render
receiver at −0.004 mm. Scale `fly_root` by 0.001 for a scene expressed in metres.

`rig.json` version 2 stores absolute local glTF quaternions `[x,y,z,w]`. Pivots
come from the measured neck, antennal sockets, oral region and leg bends.
`legs.sourcePoints` records the original joint positions. The node contract is:

```text
fly_root
└─ body_posture
   ├─ abdomen
   ├─ head
   │  ├─ antenna_L / antenna_R
   │  └─ proboscis_rostrum
   │     └─ proboscis_haustellum
   │        └─ proboscis_labellum
   │           ├─ labellum_lobe_L
   │           └─ labellum_lobe_R
   ├─ foreleg_L_coxa → foreleg_L_femur → foreleg_L_tibia → foreleg_L_tarsus
   ├─ foreleg_R_coxa → foreleg_R_femur → foreleg_R_tibia → foreleg_R_tarsus
   ├─ middleleg_L / middleleg_R
   ├─ hindleg_L / hindleg_R
   └─ wing_L / wing_R
```

## Mouth

The mouth is 3,630 source triangles before local decimation/capping, divided
between the existing oral nodes. All mouth-node scales stay at one. At feed=1,
the head bows 30°, the oral base deflects 5° and moves down only 0.018 mm. The two
halves of the source terminal tissue spread 0.0035 mm each, with a 0.0007 mm
pumping variation. There is no telescoping or fabricated extended proboscis.

The rig keeps a nectar point (`rig.mouth.nectar`, radius 0.155 mm, height about
0.102 mm) as the surface the mouth reaches in the feeding pose, but the visible
nectar drop was removed for Fly Séance: against the dark table it read as a black
bead. The mouth therefore stops about 0.1 mm above the table, with a soft contact
shadow beneath it. The canvas still clears to alpha zero.

## Forelegs and antennae

The apparent orange “horn” in the rejected combined pose was the far foreleg,
not a growing antenna. Antennal nodes keep unit scale and deflect at most 0.018
radians (1.03°). The front legs brush below and in front of the compound eyes,
using alternating targets and separate solves for the pitched feeding head.
At rest their distal segments stand beneath the head instead of stretching out.

Each foreleg now retains one continuous source surface. Four standard glTF skin
joints use the exact contract names and measured pivots; neighbouring influences
blend over 0.045 mm. Original bristles and added fine hairs use the same skin.
This removes the opening rigid seams exposed by the more folded grooming pose.
Parallel transport of segment roll prevents arbitrary half-turn twists. The
builder appends standard `JOINTS_0`, `WEIGHTS_0`, skins and inverse bind matrices
to Blender’s GLB, without an extra armature parent. Skinned mesh nodes are glTF
scene roots, as required for unambiguous skin transforms; the bones remain under
`fly_root` and carry its transform to the vertices. GLTFLoader supplies the bones;
no custom deformation shader or public API change is needed.

Drives are independently clamped to [0,1], with critically damped transitions.
Zero drive means stillness. Pump frequency is `0.42 + 1.15 × feed` Hz and grooming
is `0.32 + 1.85 × groom` Hz. Reduced motion selects a static dominant action,
feeding winning ties, and stops recurring frames. Hidden pages pause the loop.
Disposal releases the asset, materials, environment, shadows, renderer,
observers and listeners.

## Pigment and lighting

All specimen materials are `MeshPhysicalMaterial`. Pigments are assigned in
linear RGB, with anatomical variation and the source’s original pigment pattern:

- Thorax: reddish brown/caramel, darker dorsally and in cuticular grooves. Small
  dark sockets are placed at the actual source macrochaeta roots.
- Head: tan-brown with dorsal/ventral variation. Ocelli use their original surfaces
  at 65% size, coloured dark amber instead of red.
- Legs: slightly translucent pale tan distally, brown proximally, darker joints.
- Abdomen: cream ventrally, tan dorsal plates, nearly black source tergite bands,
  with extra darkening toward the tip. No pink/skin pigment is used.
- Eyes: deep brick/vermilion, roughness 0.97, minimal specular reflection, a darker
  rim, subtle view-dependent pseudopupil and antialiased hexagonal facet relief.
  Facets fade below pixel resolution to avoid moiré.
- Wings: the accepted transparent membrane, visible veins and thin-film tint.

The candle key is desaturated warm white (`#ffeee1`), with a soft cool rim and a
low reflection environment. `fly/test.html?light=neutral` selects white study
lighting through a test-canvas data attribute; the public API is unchanged.
Both lighting conditions have saved reference comparisons.

The fixed three-quarter camera remains 55° from the front and 15° above the table.
Framing support points include the actual skinned geometry across end poses.
Wide stages use 64% width, phones 86%, with an 83% height limit. Resize adjusts
distance/lens shift without changing the viewing angle.

## Verification and visual limits

`verify.mjs` serves only local files through Playwright routing. It checks exact
hierarchy and unique names, source mouth provenance, vertex colours, standard
skins, geometry budget, official glTF validation, rest poses, clamping, ongoing
motion, static supporting anatomy, planted feet, antenna contacts, unchanged
antenna/mouth scale, mouth contact with the nectar point throughout pumping, no visible nectar drop,
foreleg clearance from the table and convex eye volumes through a grooming cycle,
mouth visibility, materials, transparent canvas, wide/phone framing, reduced
motion, disposal and console errors. `verification.json` records the measurements.

`render_web.mjs` runs the project’s unchanged `scripts/shot.mjs` for ten captures:
rest/feed/groom/both (1280×520), phone (390×420), feed close (2560×1040), WebKit
combined, the real séance page (1440×900), and neutral rest/feed. Results are in
`screenshots.json`; dimensions are in `render_dimensions.json`.

The corrected colour, source mouth, matte faceted eyes and continuous grooming
remove the specific yellow/white/horn artifacts from the rejected revision.
The close view still reads as a rendered anatomical model: broad sculpted body
and leg surfaces, regular abdominal segmentation, simplified venation and limited
observed detail in the retracted source mouth remain. The original mouth is now
honest to the asset, but cannot demonstrate a fully observed feeding apparatus.
Procedural facets/hairs and real-time transmission do not reproduce photographic
microstructure or true subsurface scattering. These are the remaining realism
limits while preserving the accepted source geometry and silhouette.

## Measured budget

See `build_stats.json`, `verification.json` and `reproducibility.json` for current
counts, browser frame intervals, validation and byte-identical rebuild results.
Frame timings are active-grooming display-frame intervals on this Apple M5 Max
at DPR 1, not GPU timer queries or measurements on a physical phone.

Final asset: **189,567 triangles; 5,373,612 bytes (5.37 MB)**;
45 mesh primitives, seven specimen materials, two standard skins, no images.
Chromium median **8.2 ms**, p95 **9.0 ms**;
WebKit median **17 ms**, p95 **17 ms**.
Both suites pass with no console errors. Official glTF validation reports zero
errors and zero warnings. Rebuilding produces byte-identical output, and the
old procedural builder checksum remains unchanged.
