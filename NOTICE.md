# Third-party work

## Drosophila brain model — Shiu et al. (2024)
`src/fly_seance/brain.py` re-implements the leaky integrate-and-fire model of
https://github.com/philshiu/Drosophila_brain_model (equations, constants, and the
neuron groups in `src/fly_seance/data/groups.json`), released under:

> MIT License — Copyright (c) 2023 Philip Shiu and Nico Spiller
>
> Permission is hereby granted, free of charge, to any person obtaining a copy of
> this software and associated documentation files (the "Software"), to deal in the
> Software without restriction, including without limitation the rights to use,
> copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
> Software, and to permit persons to whom the Software is furnished to do so,
> subject to the following conditions: The above copyright notice and this
> permission notice shall be included in all copies or substantial portions of the
> Software. THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND.

Shiu, P.K. et al. A *Drosophila* computational brain model reveals sensorimotor
processing. *Nature* 634 (2024).

## FlyWire connectome
The connectome files are downloaded by `scripts/fetch_connectome.py` and are not
redistributed here. FlyWire asks users to cite:
- Dorkenwald, S. et al. Neuronal wiring diagram of an adult brain. *Nature* 634 (2024).
- Schlegel, P. et al. Whole-brain annotation and multi-connectome cell typing
  quantifies circuit stereotypy in *Drosophila*. *Nature* 634 (2024).

See https://codex.flywire.ai/about_flywire for the citation guidelines. Contributions to
FlyWire are made available under CC BY-NC 4.0 (https://flywire.ai/tos); this project
uses the data for non-commercial research and demonstration and does not redistribute it.

## Gemma
The medium runs Gemma 4, Google's open-weight model, locally through Ollama. Gemma is
not distributed with this project; Gemma 4 is released under the Apache License 2.0.

## three.js
`web/vendor/three.module.min.js` (r170) and the official addons in `web/vendor/addons/`
(GLTFLoader, BufferGeometryUtils, RoomEnvironment) are vendored unchanged from
https://github.com/mrdoob/three.js, MIT License, Copyright © 2010-2024 three.js authors.
See `web/vendor/three.LICENSE`.

## Fonts
Old Standard TT and Alegreya Sans, vendored in `web/fonts/`, are under the SIL Open
Font License 1.1 (`web/fonts/*-OFL.txt`).

## The 3D fly
The fly model is based on "Wildtype Female Drosophila Melanogaster"
(https://sketchfab.com/3d-models/wildtype-female-drosophila-melanogaster-3ba1adba62f34fe995413ee5e9cf3c25)
by mlykouretzos (https://sketchfab.com/mlykouretzos), licensed under CC BY 4.0
(http://creativecommons.org/licenses/by/4.0/). Modified for Fly Séance: decimated,
segmented, rigged, mouthparts articulated, materials changed. The rigging, the conversion
script and the animation module in `web/fly/` were generated with OpenAI Codex.
See `web/fly/MODEL-LICENSE.txt` and `web/fly/RIG.md`.

## AI assistance
The project was built with Claude Code (Anthropic) and OpenAI Codex, under the author's
direction; see "How it was built" in `README.md`. At run time the only AI is Gemma 4,
locally.
