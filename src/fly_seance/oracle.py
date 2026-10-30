"""Validate an offering, run k trials in parallel, read the fly's verdict.

The verdict is computed here, in code, from the measured firing rates of the
read-out neurons. No model takes part in it: the same rates always give the
same verdict, and the thresholds come from scripts/calibrate.py.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Callable

from fly_seance.brain import GROUPS, MAX_RATE_HZ

THRESHOLDS_PATH = Path(__file__).parent / "data" / "thresholds.json"
VOICES = ("feed", "groom", "still")


class OfferingError(ValueError):
    """The offering cannot be placed before the fly."""


class EmptyOffering(OfferingError):
    """Every rate is zero: nothing was offered."""


def validate_offering(raw: object) -> dict[str, float]:
    """Return {offering: rate in Hz} for every known offering.

    Unknown keys and non-numeric rates are refused; rates are clamped to
    [0, MAX_RATE_HZ]; an offering with nothing in it is refused."""
    if not isinstance(raw, dict):
        raise OfferingError("an offering is an object of rates")
    known = GROUPS["offerings"]
    unknown = set(raw) - set(known)
    if unknown:
        raise OfferingError(f"unknown offering(s): {sorted(unknown)}")
    rates: dict[str, float] = {}
    for name in known:
        value = raw.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OfferingError(f"{name}: rate must be a number")
        rates[name] = min(max(float(value), 0.0), MAX_RATE_HZ)
    if not any(rates.values()):
        raise EmptyOffering("the offering is empty")
    return rates


def run_trial(rates: dict[str, float], seed: int, *, silence: list[str] | tuple = (),
              duration_ms: float = 1000.0, timeout: float = 300.0) -> dict:
    """One trial in a fresh worker process (see worker.py for why)."""
    req = {"rates": rates, "seed": seed, "silence": list(silence), "duration_ms": duration_ms}
    out = subprocess.run([sys.executable, "-m", "fly_seance.worker"],
                         input=json.dumps(req), capture_output=True, text=True,
                         check=True, timeout=timeout)
    return json.loads(out.stdout)


def run_trials(rates: dict[str, float], k: int, *, silence: list[str] | tuple = (),
               seed0: int = 1, workers: int | None = None,
               on_trial: Callable[[int, dict], None] | None = None) -> list[dict]:
    """k trials with seeds seed0..seed0+k-1, in parallel; results in seed order.
    `on_trial(i, trial)` is called as each trial finishes (for live display)."""
    workers = workers or min(k, max(1, (os.cpu_count() or 2) // 2))
    results: list[dict | None] = [None] * k

    def one(i: int) -> None:
        results[i] = run_trial(rates, seed0 + i, silence=silence)
        if on_trial:
            on_trial(i, results[i])

    with ThreadPoolExecutor(max_workers=workers) as pool:
        for f in [pool.submit(one, i) for i in range(k)]:
            f.result()
    return results  # type: ignore[return-value]


def load_thresholds() -> dict:
    return json.loads(THRESHOLDS_PATH.read_text())


def _voice_rates(trial: dict) -> dict[str, float]:
    """Feed = MN9; groom = the strongest of the antennal grooming neurons."""
    r = trial["rates_hz"]
    readouts = GROUPS["readouts"]
    return {
        "feed": max(r[n] for n, ro in readouts.items() if ro["voice"] == "feed"),
        "groom": max(r[n] for n, ro in readouts.items() if ro["voice"] == "groom"),
    }


def trial_voice(trial: dict, thresholds: dict) -> str:
    """The voice of one trial: the read-out furthest above its threshold, or still."""
    v = _voice_rates(trial)
    above = {name: v[name] / thresholds[name] for name in v if v[name] >= thresholds[name]}
    return max(above, key=above.get) if above else "still"


@dataclass
class Verdict:
    voice: str                       # feed | groom | still
    agreement: float                 # share of trials that spoke with this voice
    votes: dict[str, int]
    mean_rates_hz: dict[str, float]  # per read-out neuron, over trials
    thresholds_hz: dict[str, float]
    k: int

    def to_dict(self) -> dict:
        return asdict(self)


def read_verdict(trials: list[dict], thresholds: dict | None = None) -> Verdict:
    """Majority voice over the trials; ties go to stillness (the fly did not commit)."""
    thresholds = thresholds or load_thresholds()
    votes = {voice: 0 for voice in VOICES}
    for t in trials:
        votes[trial_voice(t, thresholds)] += 1
    top = max(votes.values())
    leaders = [voice for voice in VOICES if votes[voice] == top]
    voice = leaders[0] if len(leaders) == 1 else "still"
    names = trials[0]["rates_hz"].keys()
    return Verdict(
        voice=voice,
        agreement=votes[voice] / len(trials),
        votes=votes,
        mean_rates_hz={n: round(mean(t["rates_hz"][n] for t in trials), 1) for n in names},
        thresholds_hz={k: thresholds[k] for k in ("feed", "groom")},
        k=len(trials),
    )
