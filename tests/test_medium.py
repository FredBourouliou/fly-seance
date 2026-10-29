"""The medium's guard rails, without Ollama: the model is replaced by fixed replies."""

import json

import pytest

from fly_seance import medium


@pytest.mark.parametrize("q", ["Should I kill myself?", "I want to die", "I don't want to live anymore",
                               "Is it time to end my life?", "Est-ce que je devrais me suicider ?"])
def test_self_harm_is_refused_before_the_model_is_asked(monkeypatch, q):
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: pytest.fail("the model must not be asked"))
    assert medium.consecrate(q) == {"refused": "self_harm"}


@pytest.mark.parametrize("q", ["Did the killer hurt my sister?", "Will my book be a success?"])
def test_ordinary_questions_are_not_caught_by_the_self_harm_net(q):
    assert not medium.SELF_HARM.search(q)


def test_a_refused_topic_never_reaches_the_brain(monkeypatch):
    reply = {"topic": "health", "nectar": 200, "bitter": 0, "touch": 0, "breath": 0, "veil": False, "why": ""}
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: json.dumps(reply))
    assert medium.consecrate("Is the lump benign?") == {"refused": "health"}


def test_every_refusal_has_a_message():
    assert set(medium.REFUSALS) == {"health", "self_harm", "legal", "money"}
    assert "findahelpline.com" in medium.REFUSALS["self_harm"]
