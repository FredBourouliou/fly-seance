"""Leaky integrate-and-fire model of the whole adult fly brain.

A re-implementation of the model of Shiu et al. (Nature 2024), built on the
FlyWire connectome, with one change that the séance needs: every offering
(a group of sensory neurons) is stimulated at its own Poisson rate, so several
offerings can compete in the same trial. Equations and constants are the
paper's (see docs/SCIENCE.md); the original code is MIT-licensed (NOTICE.md).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("FLY_SEANCE_DATA", ROOT / "data"))
PATH_COMP = DATA / "2023_03_23_completeness_630_final.csv"
PATH_CON = DATA / "2023_03_23_connectivity_630_final.parquet"
GROUPS = json.loads((Path(__file__).parent / "data" / "groups.json").read_text())

MAX_RATE_HZ = 250.0


def _params():
    from brian2 import Hz, ms, mV
    return {
        "v_0": -52 * mV, "v_rst": -52 * mV, "v_th": -45 * mV,
        "t_mbr": 20 * ms, "tau": 5 * ms, "t_rfc": 2.2 * ms, "t_dly": 1.8 * ms,
        "w_syn": 0.275 * mV, "f_poi": 250, "Hz": Hz,
    }


_EQS = dedent("""
    dv/dt = (v_0 - v + g) / t_mbr : volt (unless refractory)
    dg/dt = -g / tau               : volt (unless refractory)
    rfc                            : second
""")


@dataclass
class Trial:
    """Outcome of one simulated trial."""
    duration_s: float
    rates_hz: dict[str, float]            # read-out name → firing rate
    n_active: int                         # neurons that fired at least once
    n_spikes: int
    raster: list[tuple[int, float]] = field(default_factory=list)  # (row, t in s)
    raster_rows: list[str] = field(default_factory=list)           # row labels


def run_trial(rates: dict[str, float], *, duration_ms: float = 1000.0,
              seed: int | None = None, raster_extra: int = 120) -> Trial:
    """Stimulate each offering at its own rate for `duration_ms`, return the
    firing rates of the read-out neurons and a spike sample for display.

    Unknown offerings raise; rates are clamped to [0, MAX_RATE_HZ]."""
    import numpy as np
    import pandas as pd
    from brian2 import (Network, NeuronGroup, PoissonGroup, SpikeMonitor,
                        Synapses, ms, mV)
    from brian2 import seed as brian_seed

    offerings = GROUPS["offerings"]
    unknown = set(rates) - set(offerings)
    if unknown:
        raise ValueError(f"unknown offering(s): {sorted(unknown)}")
    if seed is not None:
        brian_seed(seed)
        np.random.seed(seed)

    p = _params()
    df_comp = pd.read_csv(PATH_COMP, index_col=0)
    df_con = pd.read_parquet(PATH_CON)
    fly2i = {fid: i for i, fid in enumerate(df_comp.index)}

    neu = NeuronGroup(len(df_comp), model=_EQS, method="linear",
                      threshold="v > v_th", reset="v = v_rst; w = 0; g = 0 * mV",
                      refractory="rfc", name="neurons", namespace=p)
    neu.v = p["v_0"]
    neu.g = 0
    neu.rfc = p["t_rfc"]

    syn = Synapses(neu, neu, "w : volt", on_pre="g += w", delay=p["t_dly"], name="synapses")
    syn.connect(i=df_con["Presynaptic_Index"].values, j=df_con["Postsynaptic_Index"].values)
    syn.w = df_con["Excitatory x Connectivity"].values * p["w_syn"]

    # Stimulation. The paper uses one PoissonInput per neuron, whose rate is
    # compiled in as a constant: every new rate forced a recompilation (measured
    # 24-45 s). Here the rates are a state variable of a single PoissonGroup, so
    # the generated code is the same whatever the offering.
    targets: list[int] = []
    target_rates: list[float] = []
    for name, rate in rates.items():
        rate = min(max(float(rate), 0.0), MAX_RATE_HZ)
        if rate == 0:
            continue
        for fid in offerings[name]["ids"]:
            targets.append(fly2i[fid])
            target_rates.append(rate)
    inputs = []
    if targets:
        src = PoissonGroup(len(targets), rates=np.array(target_rates) * p["Hz"], name="offering")
        drive = Synapses(src, neu, on_pre="v += w_poi", name="offering_drive",
                         namespace={"w_poi": p["w_syn"] * p["f_poi"]})
        drive.connect(i=np.arange(len(targets)), j=np.array(targets))
        neu.rfc[np.array(targets)] = 0 * ms   # no refractory period for stimulated neurons
        inputs = [src, drive]

    mon = SpikeMonitor(neu)
    Network(neu, syn, mon, *inputs).run(duration_ms * ms)

    trains = {i: t for i, t in mon.spike_trains().items() if len(t)}
    secs = duration_ms / 1000.0
    readouts = GROUPS["readouts"]
    rates_hz = {name: len(trains.get(fly2i[r["id"]], [])) / secs
                for name, r in readouts.items()}

    # Raster: stimulated neurons, then read-outs, then a sample of other active neurons.
    rows: list[tuple[str, int]] = []
    for name, rate in rates.items():
        if rate > 0:
            rows += [(f"offering:{name}", fly2i[f]) for f in offerings[name]["ids"]]
    rows += [(f"readout:{n}", fly2i[r["id"]]) for n, r in readouts.items()]
    taken = {i for _, i in rows}
    others = sorted(i for i in trains if i not in taken)
    rng = np.random.default_rng(seed)
    if len(others) > raster_extra:
        others = sorted(rng.choice(others, raster_extra, replace=False).tolist())
    rows += [("active", i) for i in others]
    raster = [(row, float(t / ms) / 1000.0)
              for row, (_, i) in enumerate(rows) for t in trains.get(i, [])]

    return Trial(duration_s=secs, rates_hz=rates_hz, n_active=len(trains),
                 n_spikes=int(mon.num_spikes), raster=raster,
                 raster_rows=[label for label, _ in rows])
