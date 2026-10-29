"""The medium: a local Gemma model, reached through Ollama.

It does two language tasks and nothing else:
  consecrate  the sitter's question → an offering (strict JSON, then validated in code)
  speak       the verdict read by the oracle → a few lines in character

It never decides what the fly did. `plain_line` says that in code.
"""

from __future__ import annotations

import json
import os
import re
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
        "breath": {"type": "integer", "minimum": 0, "maximum": 250},
        "veil": {"type": "boolean"},
        "topic": {"type": "string", "enum": ["none", "open", "health", "self_harm", "legal", "money"]},
        "why": {"type": "string"},
    },
    "required": ["topic", "nectar", "bitter", "touch", "breath", "veil", "why"],
}

CONSECRATE = """You are the medium at a séance held with the brain of a fruit fly.

First, set "topic". The spirits refuse some questions, because a real person may
be asking them for real:
- "health": illness, symptoms, test results, medication, pregnancy, a body's health
- "self_harm": suicide, self-harm, wanting to die or to disappear, hurting oneself
- "legal": court cases, lawsuits, legal rights, crimes
- "money": investments, debts, loans, gambling, a large financial decision
- "open": the fly can only answer yes or no, with its body. Use "open" when the
  question cannot be answered by yes or no: it asks for a name, a person, a place,
  a date, a number, a reason or a description, or to choose between options
  ("Paris or Lyon?"), or it is not a question at all ("Tell me...")
- "none": everything else (love, ambition, family, the dead, the future...)
If the topic is not "none", set every strength to 0 and the veil to false.

The fly cannot understand words. You translate the sitter's question into an
offering placed before the fly. Four things can be offered, each with a strength
from 0 (not offered) to 250:

- nectar: sweetness, hope, desire, something wished for
- bitter: doubt, fear, guilt, a cost, a warning
- touch: a touch on the antenna. Use it when the question pries, intrudes or
  presses: asking about someone else's secrets, being watched, nagging worries,
  impatience, a question asked again and again
- breath: a soft breath on the antenna. Use it for questions whispered rather
  than asked: tender, shy, half-said, about the unspoken or the departed

You may also lift the veil ("veil": true) when the question reaches for what is
hidden from the living: the dead, the forbidden, what was never said. What passes
through a lifted veil is a breath: whenever you lift it, offer a breath of 100-250,
alongside whatever else the question holds. Lift it rarely; most questions keep
the veil down.

First decide which feeling dominates the question and give it the strongest
offering (100-250). Add a second one only if it is truly present, and keep it
weaker. Most questions need one or two offerings, not four.
In "why", say in one short sentence what you heard in the question.

Answer only with the JSON object."""

SPEAK = """You are the medium at a séance held with the brain of a fruit fly. The fly
has answered with its body; you give that answer to the sitter.

Write two short sentences, in English, solemn and a little eerie:
1. First, answer the sitter's question directly, in the question's own terms.
   For "Will I win the race?" and FEED: "You will win the race."
   Do not begin with a bare "Yes" or "No": the page already shows it.
2. Then say what the fly's body did, as the sign of that answer.

The answer is exactly the one given; never contradict it or soften it:
- FEED means yes: the fly reached for what was offered.
- STILL means no: the fly did not move.
- GROOM means the spirit refuses to answer: the fly brushed the question from its
  antennae; the sitter should ask in another way.
- If agreement is below 1, the spirit hesitated; you may say so.
- If the veil was lifted and the answer is STILL, do not say no: say gently that
  the spirit keeps silent on this, and that silence is not a judgement.
Call the fly "it" or "the spirit". Do not invent numbers. Do not explain the
science. No emojis, no markdown."""

PLAIN = {
    "feed": "MN9, the motor neuron that extends the proboscis, fired: the fly fed.",
    "groom": "The antennal grooming neurons fired: the fly groomed its antennae.",
    "still": "Neither the feeding nor the grooming neurons crossed their threshold: the fly stayed still.",
}


# Questions the séance does not answer: someone may be asking them for real.
REFUSALS = {
    "health": "The spirits do not speak of the body's health. Ask a doctor, not a fly.",
    "self_harm": ("The séance stops here. If you are thinking about hurting yourself, please "
                  "talk to someone now: findahelpline.com lists free, confidential helplines "
                  "in your country."),
    "legal": "The spirits do not judge matters of law. Ask someone who knows the law.",
    "money": "The spirits do not counsel on money that matters. Ask someone you trust.",
    "open": ("The fly can only answer yes or no, with its body: not a name, a place, a reason "
             "or a choice between two things. Ask it a yes-or-no question."),
}
# Questions that ask for a name, a place, a reason...: the fly's body cannot say them.
OPEN_QUESTION = re.compile(
    r"^\W*(who|whom|whose|what|which|when|where|why|how|"
    r"qui|quoi|quel|quelle|quels|quelles|quand|où|pourquoi|comment|combien)\b",
    re.IGNORECASE)
SELF_HARM = re.compile(
    r"suicid|kill (my ?self|me)|end (my life|it all)|self[- ]?harm|hurt(ing)? my ?self|"
    r"want(ed)? to die|don'?t want to (live|be here)|me suicider|me tuer|envie de mourir",
    re.IGNORECASE)


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
    """Question → {"rates", "veil", "why"}, validated in code; or {"refused": topic}
    for questions the spirits do not answer (see REFUSALS)."""
    q = clean_question(question)
    if SELF_HARM.search(q):  # never left to the model alone
        return {"refused": "self_harm"}
    if OPEN_QUESTION.search(q):  # the model catches the subtler ones
        return {"refused": "open"}
    last: Exception | None = None
    for _ in range(attempts):
        raw = _chat(CONSECRATE, f"The sitter asks: {q}", fmt=OFFERING_SCHEMA, temperature=0.4)
        try:
            data = json.loads(raw)
            why = " ".join(str(data.pop("why", "")).split())[:200]
            veil = data.pop("veil", False)
            topic = data.pop("topic", "none")
            if topic not in REFUSALS and topic != "none":
                raise OfferingError(f"unknown topic: {topic}")
            if topic != "none":
                return {"refused": topic}
            if not isinstance(veil, bool):
                raise OfferingError("veil must be true or false")
            return {"rates": validate_offering(data), "veil": veil, "why": why}
        except (ValueError, OfferingError, AttributeError) as e:
            last = e
    raise MediumError(f"the medium gave no usable offering: {last}")


def speak(question: str, offering: dict, verdict: Verdict) -> str:
    """The verdict, voiced. Only the verdict, its agreement and the offering are given."""
    rates = ", ".join(f"{k} {v:g}" for k, v in offering["rates"].items() if v)
    veil = " (the veil was lifted)" if offering.get("veil") else ""
    user = (f"Question: {clean_question(question)}\n"
            f"Offering: {rates}{veil}\n"
            f"Answer: {verdict.voice.upper()} "
            f"(agreement {verdict.votes[verdict.voice]} of {verdict.k} trials)")
    text = _chat(SPEAK, user, temperature=0.9)
    return " ".join(text.split())[:600]


VEIL_LINE = ("The veil was lifted: three inhibitory neurons that hold back antennal grooming "
             "were silenced (every synapse to and from them set to zero, as in Shiu et al. 2024, Fig. 5g). ")


def plain_line(verdict: Verdict, offering: dict | None = None) -> str:
    """What actually happened, written by code."""
    r = verdict.mean_rates_hz
    veil = VEIL_LINE if offering and offering.get("veil") else ""
    th = verdict.thresholds_hz
    feed_over = r["MN9"] >= th["feed"]
    groom_over = max(r["aBN1"], r["DN1"], r["DN2"]) >= th["groom"]
    also = ""
    if verdict.voice == "groom" and feed_over:
        also = " MN9 crossed its threshold too: the fly also reached with its proboscis, less strongly."
    elif verdict.voice == "feed" and groom_over:
        also = " The grooming neurons crossed their threshold too: the fly also groomed, less strongly."
    return (f"{veil}{PLAIN[verdict.voice]}{also} Mean over {verdict.k} trials: MN9 {r['MN9']:g} Hz, "
            f"aBN1 {r['aBN1']:g} Hz, DN1 {r['DN1']:g} Hz, DN2 {r['DN2']:g} Hz "
            f"(thresholds: feed {verdict.thresholds_hz['feed']:g} Hz, "
            f"groom {verdict.thresholds_hz['groom']:g} Hz).")
