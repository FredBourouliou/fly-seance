"""One séance from the command line: question → offering → trials → verdict → voice.

    python -m fly_seance.seance "Will she come back to me?"
"""

from __future__ import annotations

import json
import sys
import time

from fly_seance.medium import consecrate, plain_line, speak
from fly_seance.oracle import read_verdict, run_trials

TRIALS = 5


def hold(question: str, k: int = TRIALS, on_trial=None) -> dict:
    t0 = time.time()
    offering = consecrate(question)
    t1 = time.time()
    trials = run_trials(offering["rates"], k, on_trial=on_trial)
    t2 = time.time()
    verdict = read_verdict(trials)
    voice = speak(question, offering, verdict)
    t3 = time.time()
    return {
        "question": question,
        "offering": offering,
        "verdict": verdict.to_dict(),
        "voice": voice,
        "plain": plain_line(verdict),
        "seconds": {"consecrate": round(t1 - t0, 1), "channel": round(t2 - t1, 1),
                    "speak": round(t3 - t2, 1)},
        "trials": trials,
    }


def main() -> None:
    question = " ".join(sys.argv[1:]) or input("Your question: ")
    s = hold(question)
    print(json.dumps({k: v for k, v in s.items() if k != "trials"}, indent=1))


if __name__ == "__main__":
    main()
