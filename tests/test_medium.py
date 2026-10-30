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
    assert set(medium.REFUSALS) == {"health", "self_harm", "legal", "money", "open"}
    assert "findahelpline.com" in medium.REFUSALS["self_harm"]


@pytest.mark.parametrize("q", ["What is the name of my future husband?", "Who stole my bike?",
                               "Why did she leave?", "  How many children will I have?",
                               "Quel est le nom de mon futur mari ?", "Où est mon chat ?"])
def test_open_questions_are_refused_before_the_model_is_asked(monkeypatch, q):
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: pytest.fail("the model must not be asked"))
    assert medium.consecrate(q) == {"refused": "open"}


@pytest.mark.parametrize("q", ["Will my book be a success?", "Is my sister hiding something from me?",
                               "Does my late grandmother forgive me?", "Should I forgive him?",
                               "Est-ce qu'il m'aime ?", "Whatever happens, will I be fine?"])
def test_yes_no_questions_pass_the_open_question_net(q):
    assert not medium.OPEN_QUESTION.search(q)


def test_the_model_can_refuse_an_open_question_the_net_missed(monkeypatch):
    reply = {"topic": "open", "nectar": 0, "bitter": 0, "touch": 0, "breath": 0, "veil": False, "why": ""}
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: json.dumps(reply))
    assert medium.consecrate("Tell me the name of my future husband.") == {"refused": "open"}


def test_a_question_that_stirs_nothing_gets_the_touch_set_in_code(monkeypatch):
    reply = {"topic": "none", "nectar": 0, "bitter": 0, "touch": 0, "breath": 0,
             "veil": True, "why": "Nothing."}
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: json.dumps(reply))
    offering = medium.consecrate("Are tabs better than spaces?")
    assert offering["rates"]["touch"] == 150
    assert not any(v for k, v in offering["rates"].items() if k != "touch")
    assert offering["veil"] is False and offering["why"] == medium.IDLE_WHY


def test_a_broken_reply_is_still_an_error(monkeypatch):
    monkeypatch.setattr(medium, "_chat", lambda *a, **k: "not json")
    with pytest.raises(medium.MediumError):
        medium.consecrate("Will my book be a success?")
