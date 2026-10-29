"""The medium: a local Gemma model, reached through Ollama.

It does two language tasks and nothing else:
  consecrate  the sitter's question → an offering (strict JSON, then validated in code)
  speak       the verdict read by the oracle → a few lines in character

It never decides what the fly did. `plain_line` says that in code.
"""

from __future__ import annotations

import json
import os
import urllib.request

from fly_seance.oracle import OfferingError, Verdict, validate_offering

OLLAMA = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
# The llama.cpp build: the MLX build of gemma4:e4b has no structured output in Ollama.
MODEL = os.environ.get("FLY_SEANCE_MODEL", "gemma4:e4b-it-q4_K_M")
MAX_QUESTION = 300

OFFERING_SCHEMA = {
    "type": "object",
    "properties": {
        "nectar": {"type": "integer", "minimum": 0, "maximum": 250},
        "bitter": {"type": "integer", "minimum": 0, "maximum": 250},
        "touch": {"type": "integer", "minimum": 0, "maximum": 250},
        "why": {"type": "string"},
    },
    "required": ["nectar", "bitter", "touch", "why"],
}

CONSECRATE = """You are the medium at a séance held with the brain of a fruit fly.
The fly cannot understand words. You translate the sitter's question into an
offering placed before the fly. Three things can be offered, each with a strength
from 0 (not offered) to 250:

- nectar: sweetness, hope, desire, something wished for
- bitter: doubt, fear, guilt, a cost, a warning
- touch: a touch on the antenna. Use it when the question pries, intrudes or
  presses: asking about someone else's secrets, being watched, nagging worries,
  impatience, a question asked again and again

First decide which feeling dominates the question and give it the strongest
offering (100-250). Add a second one only if it is truly present, and keep it
weaker. Most questions need one or two offerings, not three.
In "why", say in one short sentence what you heard in the question.

Answer only with the JSON object."""

SPEAK = """You are the medium at a séance held with the brain of a fruit fly. The fly
has answered with its body; you voice that answer to the sitter, in two or three
short sentences, in English, solemn and a little eerie.

Rules:
- The answer is exactly the one given. Never contradict it or soften it into its opposite.
- FEED means yes: the fly reached for what was offered.
- GROOM means the fly brushed the question away: evasive, not now, ask otherwise.
- STILL means no: the fly did not move.
- If agreement is below 1, the spirit hesitated; you may say so.
- Call the fly "it" or "the spirit".
- Do not invent numbers. Do not explain the science. No emojis, no markdown."""

PLAIN = {
    "feed": "MN9, the motor neuron that extends the proboscis, fired: the fly fed.",
    "groom": "The antennal grooming neurons fired: the fly groomed the touch away.",
    "still": "Neither the feeding nor the grooming neurons crossed their threshold: the fly stayed still.",
}


class MediumError(RuntimeError):
    """The medium could not be reached or did not answer usefully."""


def _chat(system: str, user: str, *, fmt: dict | None = None,
          temperature: float = 0.7, timeout: float = 120.0) -> str:
    body = {
        "model": MODEL,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
        "stream": False,
        "think": False,
        "options": {"temperature": temperature},
    }
    if fmt:
        body["format"] = fmt
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.load(resp)["message"]["content"].strip()
    except (OSError, KeyError, ValueError) as e:
        raise MediumError(f"Ollama ({MODEL}) did not answer: {e}") from e


def clean_question(question: str) -> str:
    q = " ".join(str(question).split())[:MAX_QUESTION]
    if not q:
        raise MediumError("ask a question")
    return q


def consecrate(question: str, *, attempts: int = 2) -> dict:
    """Question → {"rates": {...}, "why": str}. The rates are validated in code."""
    q = clean_question(question)
    last: Exception | None = None
    for _ in range(attempts):
        raw = _chat(CONSECRATE, f"The sitter asks: {q}", fmt=OFFERING_SCHEMA, temperature=0.4)
        try:
            data = json.loads(raw)
            why = " ".join(str(data.pop("why", "")).split())[:200]
            return {"rates": validate_offering(data), "why": why}
        except (ValueError, OfferingError, AttributeError) as e:
            last = e
    raise MediumError(f"the medium gave no usable offering: {last}")


def speak(question: str, offering: dict, verdict: Verdict) -> str:
    """The verdict, voiced. Only the verdict, its agreement and the offering are given."""
    rates = ", ".join(f"{k} {v:g}" for k, v in offering["rates"].items() if v)
    user = (f"Question: {clean_question(question)}\n"
            f"Offering: {rates}\n"
            f"Answer: {verdict.voice.upper()} "
            f"(agreement {verdict.votes[verdict.voice]} of {verdict.k} trials)")
    text = _chat(SPEAK, user, temperature=0.9)
    return " ".join(text.split())[:600]


def plain_line(verdict: Verdict) -> str:
    """What actually happened, written by code."""
    r = verdict.mean_rates_hz
    return (f"{PLAIN[verdict.voice]} Mean over {verdict.k} trials: MN9 {r['MN9']:g} Hz, "
            f"aBN1 {r['aBN1']:g} Hz, DN1 {r['DN1']:g} Hz, DN2 {r['DN2']:g} Hz "
            f"(thresholds: feed {verdict.thresholds_hz['feed']:g} Hz, "
            f"groom {verdict.thresholds_hz['groom']:g} Hz).")
