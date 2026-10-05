"""Deterministic Bayesian Knowledge Tracing (BKT) v1 service.

Pure mathematical functions for learner concept mastery estimation.
- Pure and deterministic
- Zero LLM usage
- Zero network or external I/O
- Zero randomness
- Rejects NaN, +/- infinity, and out-of-range probabilities
- Guarded zero denominator
- Numerical saturation guard (BKT_MAX_MASTERY)
"""

from dataclasses import dataclass
import math

# BKT v1 model constants
BKT_INITIAL_MASTERY: float = 0.20
BKT_LEARN_PROBABILITY: float = 0.10
BKT_GUESS_PROBABILITY: float = 0.20
BKT_SLIP_PROBABILITY: float = 0.10
BKT_MODEL_VERSION: str = "bkt-v1"
BKT_MAX_MASTERY: float = 1.0 - 1e-12


@dataclass(frozen=True)
class BKTStepResult:
    """Result of a single deterministic BKT step calculation."""

    prior_mastery: float
    posterior_mastery: float
    updated_mastery: float
    learn_probability: float
    guess_probability: float
    slip_probability: float
    model_version: str


def validate_probability(value: float, name: str) -> None:
    """Validate that a probability value is a finite number in [0.0, 1.0]."""
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a real number, got bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a real number, got {type(value).__name__}")
    if value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be in [0.0, 1.0], got {value}")
    if math.isnan(value):
        raise ValueError(f"{name} cannot be NaN")
    if math.isinf(value):
        raise ValueError(f"{name} cannot be infinite")


def compute_bkt_step(
    prior: float,
    is_correct: bool,
    *,
    learn_p: float = BKT_LEARN_PROBABILITY,
    guess_p: float = BKT_GUESS_PROBABILITY,
    slip_p: float = BKT_SLIP_PROBABILITY,
    model_version: str = BKT_MODEL_VERSION,
) -> BKTStepResult:
    """Compute the next BKT mastery probability given an attempt correctness.

    Formulas:
      Correct:
        posterior = p * (1 - S) / (p * (1 - S) + (1 - p) * G)
      Incorrect:
        posterior = p * S / (p * S + (1 - p) * (1 - G))
      Learning transition:
        updated = posterior + (1 - posterior) * T
      Saturation guard:
        updated_mastery = min(updated, BKT_MAX_MASTERY)
    """
    if not isinstance(is_correct, bool):
        raise ValueError(f"is_correct must be a bool, got {type(is_correct).__name__}")

    validate_probability(prior, "prior")
    validate_probability(learn_p, "learn_p")
    validate_probability(guess_p, "guess_p")
    validate_probability(slip_p, "slip_p")

    p = float(prior)
    t = float(learn_p)
    g = float(guess_p)
    s = float(slip_p)

    if is_correct:
        num = p * (1.0 - s)
        denom = num + (1.0 - p) * g
    else:
        num = p * s
        denom = num + (1.0 - p) * (1.0 - g)

    if denom <= 0.0:
        raise ValueError(f"Invalid BKT parameters caused zero denominator: p={p}, t={t}, g={g}, s={s}, is_correct={is_correct}")

    posterior = num / denom

    # Keep posterior within [0.0, 1.0]
    posterior = max(0.0, min(1.0, posterior))

    # Learning transition
    raw_updated = posterior + (1.0 - posterior) * t
    raw_updated = max(0.0, min(1.0, raw_updated))

    # Numerical saturation guard: prevent absorbing certainty p=1.0
    guarded_updated = min(raw_updated, BKT_MAX_MASTERY)

    return BKTStepResult(
        prior_mastery=p,
        posterior_mastery=posterior,
        updated_mastery=guarded_updated,
        learn_probability=t,
        guess_probability=g,
        slip_probability=s,
        model_version=model_version,
    )


def get_mastery_band(observation_count: int, mastery_probability: float) -> str:
    """Compute presentation-only mastery band.

    observation_count == 0: unseen
    p < 0.40: needs_work
    0.40 <= p < 0.70: developing
    0.70 <= p < 0.90: strong
    p >= 0.90: mastered
    """
    if observation_count == 0:
        return "unseen"
    if mastery_probability < 0.40:
        return "needs_work"
    if mastery_probability < 0.70:
        return "developing"
    if mastery_probability < 0.90:
        return "strong"
    return "mastered"
