# Architecture

Fly Séance holds a séance with a simulated fruit-fly brain. A local Gemma model
is the medium; the fly's real wiring diagram decides what its body would do.

```
  sitter's question
        │
        ▼
 ┌──────────────┐  1. CONSECRATE        offering = {nectar Hz, bitter Hz, touch Hz}
 │ Gemma (local)│ ───────────────────►  strict JSON, validated and clamped in code
 └──────────────┘
        │
        ▼
 ┌────────────────────────────┐  2. CHANNEL   leaky integrate-and-fire model of
 │ connectome simulation       │  ───────────► the whole adult fly brain
 │ (Brian 2, ~139k neurons)    │              (FlyWire wiring, Shiu et al. 2024)
 └────────────────────────────┘              k trials × 1 s, one process per trial
        │  firing rates of read-out neurons + a spike sample for the raster
        ▼
 ┌──────────────┐  3. READ          deterministic, in code — never the model:
 │ verdict      │ ─────────────────► FEED (MN9) · GROOM (aBN1, DN1, DN2) · STILL
 └──────────────┘
        │
        ▼
 ┌──────────────┐  4. SPEAK         Gemma narrates in character, given ONLY the
 │ Gemma (local)│ ─────────────────► verdict and the measured numbers; the plain
 └──────────────┘                    "what actually happened" line is written by code
        │
        ▼
   web page (Server-Sent Events): offering → live spike raster → verdict → voice
```

## Why each piece is there

| Step | Who | Why not the other one |
|------|-----|-----------------------|
| Consecrate | Gemma | Turning a free-text question into a sensory offering is a language task. |
| Channel | connectome | The arbitration between offerings (bitter suppresses feeding, touch triggers grooming) comes from real wiring, not from a prompt. |
| Read | code | The verdict must be reproducible and auditable; a model must not "decide" what the fly did. |
| Speak | Gemma | Voice and atmosphere; constrained to the verdict and numbers it is handed. |

The fly does not understand the question. What is real is the body's response to
the offering, computed from the wiring of an actual fly. The write-up says so.

## Offerings → sensory neurons (stimulated as Poisson input)

| Offering | Neurons stimulated (FlyWire 630 IDs) | Validated in Shiu et al. 2024 |
|----------|--------------------------------------|-------------------------------|
| nectar | 21 labellar sugar GRNs, right hemisphere | Fig. 1, 3 |
| bitter herb | 21 labellar bitter GRNs | Fig. 3 (suppresses sugar → MN9) |
| touch on the antenna | 70 Johnston's organ CE neurons (JON-CE) | Fig. 5 (antennal grooming) |

Each offering has its own rate (0–250 Hz); 0 means "not offered".

## Read-out neurons (the fly's "voices")

| Voice | Neurons | Meaning in the séance |
|-------|---------|-----------------------|
| FEED | MN9 (proboscis motor neuron) | the spirit accepts — "yes" |
| GROOM | aBN1, aDN1 (DN1), aDN2 (DN2) | the spirit brushes it off — evasive |
| STILL | neither above threshold | silence — "no" |

Thresholds are calibrated from baseline runs (`scripts/calibrate.py`), not chosen by hand.

## Process model

- The paper's code gives each stimulated neuron a `PoissonInput` whose rate is
  compiled in as a constant: every new rate recompiled the network (measured 24–45 s).
  `brain.py` drives the offerings from one `PoissonGroup` whose rates are a state
  variable, so the generated code is identical for any offering: 3–4 s per trial
  after a one-off ~8 s compilation.
- Within a single process, later trials were measured several times slower than the
  first. Each trial therefore runs in a **fresh worker process**
  (`python -m fly_seance.worker`), and k trials run in parallel (18 cores available).
- Measured on the dev machine (M5 Max, 48 GB): ~2.2 GB RAM per worker.
- Gemma 4 E4B via Ollama (`localhost:11434`): ~5 s per narration.

## Modules

| Path | Role |
|------|------|
| `src/fly_seance/data/groups.json` | FlyWire IDs of offerings and read-outs (from the paper's notebook) |
| `src/fly_seance/brain.py` | LIF model: load connectome, stimulate N groups at their own rates, return rates |
| `src/fly_seance/worker.py` | one trial per process, JSON in / JSON out |
| `src/fly_seance/oracle.py` | offering validation, parallel trials, verdict |
| `src/fly_seance/medium.py` | Ollama client: consecrate (JSON offering) and speak (narration) |
| `src/fly_seance/server.py` | standard-library HTTP + SSE server for the page |
| `web/` | the séance page |
| `scripts/fetch_connectome.py` | downloads the connectome files (not redistributed here) |
| `scripts/calibrate.py` | baseline runs → thresholds |

## Data

The connectome files are **downloaded, not committed**: `scripts/fetch_connectome.py`
fetches them from the Shiu et al. repository (MIT) into `data/`. The FlyWire
resource asks to be cited; see `NOTICE.md`.
