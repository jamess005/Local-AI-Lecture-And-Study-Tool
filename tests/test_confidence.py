import pytest
from src.confidence import get_score, update_score, pick_by_confidence, score_key


def test_score_key_format():
    assert score_key("Maths", "Set Theory", "Sets") == "Maths/Set Theory/Sets"


def test_get_score_default():
    assert get_score({}, "Maths/Set Theory/Sets") == 0.5


def test_get_score_existing():
    assert get_score({"Maths/Set Theory/Sets": 0.8}, "Maths/Set Theory/Sets") == 0.8


def test_update_correct_increases():
    scores = {"Maths/Set Theory/Sets": 0.5}
    result = update_score(scores, "Maths/Set Theory/Sets", "Correct")
    assert result["Maths/Set Theory/Sets"] == pytest.approx(0.6)


def test_update_incorrect_decreases():
    scores = {"Maths/Set Theory/Sets": 0.5}
    result = update_score(scores, "Maths/Set Theory/Sets", "Incorrect")
    assert result["Maths/Set Theory/Sets"] == pytest.approx(0.4)


def test_update_partial_unchanged():
    scores = {"Maths/Set Theory/Sets": 0.5}
    result = update_score(scores, "Maths/Set Theory/Sets", "Partial")
    assert result["Maths/Set Theory/Sets"] == pytest.approx(0.5)


def test_update_clamps_at_one():
    scores = {"Maths/Set Theory/Sets": 1.0}
    result = update_score(scores, "Maths/Set Theory/Sets", "Correct")
    assert result["Maths/Set Theory/Sets"] == 1.0


def test_update_clamps_at_zero():
    scores = {"Maths/Set Theory/Sets": 0.0}
    result = update_score(scores, "Maths/Set Theory/Sets", "Incorrect")
    assert result["Maths/Set Theory/Sets"] == 0.0


def test_pick_by_confidence_returns_tuple():
    notes = {"Maths": {"Set Theory": {"Sets": "content"}}}
    scores = {}
    subject, subtopic, topic, content = pick_by_confidence(notes, scores)
    assert subject == "Maths"
    assert subtopic == "Set Theory"
    assert topic == "Sets"
    assert content == "content"
