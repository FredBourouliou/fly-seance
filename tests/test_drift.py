"""Between questions: random stimuli, decided by the brain."""

import random

import pytest

from fly_seance import drift
from fly_seance.brain import GROUPS, PATH_COMP, PATH_CON


def test_draws_are_known_offerings_within_range():
    rng = random.Random(7)
    for _ in range(200):
        kind, hz = drift.draw(rng)
        assert kind in GROUPS["offerings"] and kind in drift.STIMULI
        assert drift.RATE_HZ[0] <= hz <= drift.RATE_HZ[1]


@pytest.mark.skipif(not (PATH_COMP.exists() and PATH_CON.exists()), reason="connectome files not fetched")
def test_feel_reads_the_voice_from_the_brain():
    out = drift.feel(seed=3)
    assert out["voice"] in ("feed", "groom", "still")
    assert set(out["rates_hz"]) == {"MN9", "aBN1", "DN1", "DN2"}
