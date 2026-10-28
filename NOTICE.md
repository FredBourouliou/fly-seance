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

See https://codex.flywire.ai/about_flywire for the citation guidelines.

## Gemma
The medium runs Gemma, Google's open-weight model, locally through Ollama. Gemma is
not distributed with this project; its use is subject to Google's Gemma terms.
