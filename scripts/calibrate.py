"""Run a grid of offerings and write the raw read-out rates to results/.

    python scripts/calibrate.py            # grid → results/calibration.json
    python scripts/calibrate.py --report   # summary of an existing run
    python scripts/calibrate.py --thresholds   # derive thresholds.json from the run

The model has no spontaneous activity (every read-out is exactly 0 without an
effective offering), and each voice's rates fall into two separate bands: weak
flickers (a few spikes) and real drive. Each threshold is the midpoint of the
first empty band of at least MIN_GAP_HZ above zero; any threshold inside that
band gives the same verdict on every calibration trial.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from fly_seance.oracle import THRESHOLDS_PATH, _voice_rates, run_trials

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "calibration.json"
LEVELS = [10, 25, 50, 100, 150, 250]
SEEDS = 3
MIN_GAP_HZ = 8


def grid() -> list[dict]:
    """Offerings; the key "veil": True means the veil group is silenced."""
    conds = [{name: hz} for name in ("nectar", "bitter", "touch", "breath") for hz in LEVELS]
    conds += [{"breath": hz, "veil": True} for hz in LEVELS]
    conds += [
        {"touch": 150, "veil": True},
        {"nectar": 150, "veil": True},
        {"nectar": 150, "breath": 150, "veil": True},
    ]
    conds += [
        {"nectar": 150, "bitter": 150},
        {"nectar": 150, "bitter": 50},
        {"nectar": 150, "touch": 150},
        {"nectar": 150, "touch": 50},
        {"nectar": 50, "touch": 150},
        {"bitter": 150, "touch": 150},
    ]
    return conds


def run() -> None:
    rows = []
    t0 = time.time()
    for cond in grid():
        rates = {k: v for k, v in cond.items() if k != "veil"}
        silence = ["veil"] if cond.get("veil") else []
        trials = run_trials(rates, SEEDS, silence=silence, workers=SEEDS)
        for seed, t in enumerate(trials, 1):
            rows.append({"offering": cond, "seed": seed, "rates_hz": t["rates_hz"],
                         "n_active": t["n_active"]})
        print(cond, [t["rates_hz"] for t in trials], flush=True)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps({"seconds": round(time.time() - t0), "rows": rows}, indent=1))
    print(f"→ {OUT} ({round(time.time() - t0)} s)")


def report() -> None:
    rows = json.loads(OUT.read_text())["rows"]
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(json.dumps(r["offering"]), []).append(r["rates_hz"])
    for cond, rs in by.items():
        cells = " ".join(f"{n}={min(x[n] for x in rs):>5.0f}-{max(x[n] for x in rs):<5.0f}"
                         for n in rs[0])
        print(f"{cond:<36} {cells}")


def first_gap(values: list[float]) -> tuple[float, float]:
    """The first empty band of at least MIN_GAP_HZ between non-zero rates."""
    xs = sorted({v for v in values if v > 0})
    for lo, hi in zip([0.0] + xs, xs):
        if hi - lo >= MIN_GAP_HZ:
            return lo, hi
    raise SystemExit("no empty band: the read-out does not separate")


def thresholds() -> None:
    rows = json.loads(OUT.read_text())["rows"]
    voices = [_voice_rates(r) for r in rows]
    out = {"_source": f"scripts/calibrate.py on {len(rows)} trials; midpoint of the first "
                      f"empty band >= {MIN_GAP_HZ} Hz", "bands_hz": {}}
    for name in ("feed", "groom"):
        lo, hi = first_gap([v[name] for v in voices])
        out[name] = (lo + hi) / 2
        out["bands_hz"][name] = [lo, hi]
        print(f"{name}: empty band {lo:g}-{hi:g} Hz -> threshold {out[name]:g} Hz")
    THRESHOLDS_PATH.write_text(json.dumps(out, indent=1) + "\n")
    print(f"-> {THRESHOLDS_PATH}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--report", action="store_true")
    g.add_argument("--thresholds", action="store_true")
    a = ap.parse_args()
    report() if a.report else thresholds() if a.thresholds else run()
