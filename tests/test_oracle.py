"""The verdict is read in code, from the rates alone. No connectome needed here."""

import pytest

from fly_seance.oracle import OfferingError, read_verdict, validate_offering

TH = {"feed": 10.5, "groom": 13.0}


def t(mn9=0.0, abn1=0.0, dn1=0.0, dn2=0.0):
    return {"rates_hz": {"MN9": mn9, "aBN1": abn1, "DN1": dn1, "DN2": dn2}}


def test_offering_is_completed_and_clamped():
    assert validate_offering({"nectar": 400, "touch": -5}) == {
        "nectar": 250.0, "bitter": 0.0, "touch": 0.0, "breath": 0.0}


@pytest.mark.parametrize("raw", [
    {"blood": 100},            # unknown offering
    {"nectar": "a lot"},       # not a number
    {"nectar": True},          # a bool is not a rate
    {"nectar": 0, "touch": 0},  # nothing offered
    [150],                     # not an object
])
def test_bad_offerings_are_refused(raw):
    with pytest.raises(OfferingError):
        validate_offering(raw)


def test_feed_groom_still():
    assert read_verdict([t(mn9=80)] * 3, TH).voice == "feed"
    assert read_verdict([t(abn1=50, dn2=20)] * 3, TH).voice == "groom"
    assert read_verdict([t(mn9=6, abn1=3)] * 3, TH).voice == "still"


def test_both_voices_the_stronger_relative_to_its_threshold_wins():
    assert read_verdict([t(mn9=80, abn1=51)], TH).voice == "feed"
    assert read_verdict([t(mn9=18, abn1=51)], TH).voice == "groom"


def test_groom_listens_to_every_grooming_neuron():
    assert read_verdict([t(dn1=30)], TH).voice == "groom"


def test_majority_and_agreement():
    v = read_verdict([t(mn9=80), t(mn9=80), t()], TH)
    assert v.voice == "feed" and v.votes == {"feed": 2, "groom": 0, "still": 1}
    assert v.agreement == pytest.approx(2 / 3)
    assert v.mean_rates_hz["MN9"] == pytest.approx(53.3)


def test_a_tie_is_stillness():
    assert read_verdict([t(mn9=80), t(abn1=50)], TH).voice == "still"


def test_raster_thinning_keeps_every_readout_spike():
    from fly_seance.server import thin_raster
    rows = ["offering:nectar"] * 10 + ["readout:MN9"]
    raster = [(r, t / 1000) for r in range(10) for t in range(1000)] + [(10, t / 100) for t in range(80)]
    thin = thin_raster(rows, raster, limit=500)
    assert len(thin) == 500
    assert sum(1 for r, _ in thin if r == 10) == 80
