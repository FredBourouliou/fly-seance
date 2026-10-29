"""The connectome model reproduces the paper's behaviours, and offerings compete.

Each trial runs in a fresh worker process, as the oracle does. These tests need the
connectome files (python scripts/fetch_connectome.py); they are skipped otherwise.
"""

import json
import subprocess
import sys

import pytest

from fly_seance.brain import PATH_CON, PATH_COMP, run_trial

needs_data = pytest.mark.skipif(not (PATH_COMP.exists() and PATH_CON.exists()),
                                reason="connectome files not fetched")


def trial(rates, seed=1):
    out = subprocess.run([sys.executable, "-m", "fly_seance.worker"],
                         input=json.dumps({"rates": rates, "seed": seed}),
                         capture_output=True, text=True, check=True, timeout=300)
    return json.loads(out.stdout)


def test_unknown_offering_is_refused():
    with pytest.raises(ValueError):
        run_trial({"blood": 100})


@needs_data
def test_nectar_drives_the_proboscis():
    r = trial({"nectar": 150})["rates_hz"]
    assert r["MN9"] > 40
    assert r["aBN1"] == 0


@needs_data
def test_bitter_alone_drives_nothing():
    r = trial({"bitter": 150})["rates_hz"]
    assert r["MN9"] == 0 and r["aBN1"] == 0


@needs_data
def test_touch_on_the_antenna_drives_grooming_not_feeding():
    r = trial({"touch": 150})["rates_hz"]
    assert r["aBN1"] > 20
    assert r["MN9"] == 0


@needs_data
def test_bitter_suppresses_nectar():
    alone = trial({"nectar": 150})["rates_hz"]["MN9"]
    mixed = trial({"nectar": 150, "bitter": 150})["rates_hz"]["MN9"]
    assert mixed < alone / 2


@needs_data
def test_rates_are_clamped_and_zero_means_not_offered():
    d = trial({"nectar": 10_000, "touch": 0})
    assert d["rates_hz"]["MN9"] > 0
    assert not any(row.startswith("offering:touch") for row in d["raster_rows"])


@needs_data
def test_a_breath_alone_is_ignored_but_the_veil_unmasks_grooming():
    # Shiu et al. 2024, Fig. 5g: silencing three inhibitory neurons lets JON-F drive grooming.
    alone = trial({"breath": 150})["rates_hz"]
    veiled = run_veiled({"breath": 150})["rates_hz"]
    assert alone["aBN1"] < 5
    assert veiled["aBN1"] > 20 and veiled["MN9"] == 0


@needs_data
def test_the_veil_leaves_feeding_alone():
    assert run_veiled({"nectar": 150})["rates_hz"]["MN9"] > 40


def test_unknown_group_to_silence_is_refused():
    with pytest.raises(ValueError):
        run_trial({"nectar": 100}, silence=["everything"])


def run_veiled(rates, seed=1):
    out = subprocess.run([sys.executable, "-m", "fly_seance.worker"],
                         input=json.dumps({"rates": rates, "silence": ["veil"], "seed": seed}),
                         capture_output=True, text=True, check=True, timeout=300)
    return json.loads(out.stdout)
