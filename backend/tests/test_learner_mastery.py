"""Deterministic BKT contracts, including numerical and type boundaries."""

import pytest

from app.services.learner_mastery import (
    BKT_MAX_MASTERY,
    compute_bkt_step,
    get_mastery_band,
)
from app.schemas.learner_mastery import MasteryBand


@pytest.mark.parametrize("correct,posterior,updated", [
    (True, 9 / 17, 49 / 85),
    (False, 1 / 33, 7 / 55),
])
def test_exact_step(correct, posterior, updated):
    result = compute_bkt_step(.2, correct)
    assert result.prior_mastery == .2
    assert result.posterior_mastery == pytest.approx(posterior)
    assert result.updated_mastery == pytest.approx(updated)
    assert (result.learn_probability, result.guess_probability, result.slip_probability) == (.1, .2, .1)
    assert result.model_version == "bkt-v1"


@pytest.mark.parametrize("name", ["prior", "learn_p", "guess_p", "slip_p"])
@pytest.mark.parametrize("value", [True, False, float("nan"), float("inf"), -float("inf"), -.01, 1.01, "0.2"])
def test_invalid_probabilities(name, value):
    args = {"prior": .2, "is_correct": True, name: value}
    with pytest.raises(ValueError):
        compute_bkt_step(**args)


@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_correctness_must_be_boolean(value):
    with pytest.raises(ValueError, match="is_correct must be a bool"):
        compute_bkt_step(.2, value)


@pytest.mark.parametrize("correct,kwargs", [
    (True, {"prior": 0, "guess_p": 0}),
    (False, {"prior": 1, "slip_p": 0}),
])
def test_zero_denominator(correct, kwargs):
    with pytest.raises(ValueError, match="zero denominator"):
        compute_bkt_step(is_correct=correct, **kwargs)


def test_saturation_guard_and_recovery():
    p = .2
    for _ in range(100):
        p = compute_bkt_step(p, True).updated_mastery
    assert p == BKT_MAX_MASTERY < 1
    assert compute_bkt_step(p, False).updated_mastery < p


def test_mixed_order_is_deterministic():
    def sequence(outcomes):
        p = .2
        for outcome in outcomes:
            p = compute_bkt_step(p, outcome).updated_mastery
        return p
    assert sequence([True, False]) == pytest.approx(.2308605341246291)
    assert sequence([False, True]) == pytest.approx(.45660377358490567)
    assert sequence([True, False]) == sequence([True, False])


@pytest.mark.parametrize("count,p,expected", [
    (0, .2, MasteryBand.unseen), (1, .39, MasteryBand.needs_work),
    (1, .4, MasteryBand.developing), (1, .7, MasteryBand.strong),
    (1, .9, MasteryBand.mastered),
])
def test_band_boundaries(count, p, expected):
    assert get_mastery_band(count, p) == expected
