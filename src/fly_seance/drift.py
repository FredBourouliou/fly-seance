"""Between questions, the fly feels the room.

A small stimulus is drawn at random (a speck of sugar, a draught on the antenna...)
and sent to the simulated brain for one trial. No model is involved: whether the
fly reacts, and how, is decided by the connectome alone. Most draws do nothing;
some make it feed or groom.
"""

from __future__ import annotations

import random

from fly_seance.oracle import load_thresholds, run_trial, trial_voice

# What the room may offer, and how the page tells it.
STIMULI = {
    "nectar": "A speck of sugar on the table",
    "bitter": "A bitter crumb nearby",
    "touch": "A draught brushes the antenna",
    "breath": "Something breathes close by",
}
RATE_HZ = (20, 220)


def draw(rng: random.Random) -> tuple[str, int]:
    kind = rng.choice(sorted(STIMULI))
    return kind, rng.randrange(RATE_HZ[0], RATE_HZ[1] + 1, 10)


def feel(seed: int | None = None) -> dict:
    """One random stimulus, one trial; the voice is read in code as in a séance."""
    rng = random.Random(seed)
    kind, hz = draw(rng)
    trial = run_trial({kind: hz}, seed=rng.randrange(1, 2**31))
    return {
        "stimulus": kind,
        "rate_hz": hz,
        "what": STIMULI[kind],
        "voice": trial_voice(trial, load_thresholds()),
        "rates_hz": trial["rates_hz"],
    }
