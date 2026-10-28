"""Run one trial in this process: JSON request on stdin, JSON result on stdout.

Brian 2 recompiles for every new network, and later networks in the same
process were measured several times slower than the first. The oracle therefore
starts one worker process per trial.

    echo '{"rates": {"nectar": 150}, "seed": 1}' | python -m fly_seance.worker
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict

from fly_seance.brain import run_trial


def main() -> None:
    req = json.load(sys.stdin)
    trial = run_trial(req["rates"], duration_ms=float(req.get("duration_ms", 1000)),
                      seed=req.get("seed"))
    json.dump(asdict(trial), sys.stdout)


if __name__ == "__main__":
    main()
