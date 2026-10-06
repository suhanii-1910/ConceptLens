"""Deterministic grounding metrics; these are NOT RAGAS metrics."""
from collections import Counter
from statistics import mean
from .dataset import Case, Locator


def ratio(n: float, d: float) -> float | None:
    return n / d if d else None


def locator_matches(expected: dict, actual: dict) -> bool:
    try:
        e, a = Locator.model_validate(expected), Locator.model_validate(actual)
    except (ValueError, TypeError):
        return False
    if e.kind != a.kind:
        return False
    if e.kind != "time":
        return e.number == a.number
    if e.start == e.end:
        return a.start <= e.start <= a.end
    # At least half the expected interval must be covered. No filename-only credit.
    return max(0, min(e.end, a.end) - max(e.start, a.start)) / (e.end - e.start) >= 0.5


def matches(expected: dict, actual: dict) -> bool:
    return expected["source_id"] == actual.get("source_id") and locator_matches(expected["locator"], actual.get("locator", {}))


def case_metrics(case: Case, result: dict) -> dict:
    if result["status"] not in {"answered", "declined"}:
        return {"scored": False, "reason": "execution error or pending provider"}
    expected = [e.model_dump() for e in case.expected]
    citations, retrieved = result["citations"], result["retrieved"]
    source_hits = sum(c.get("source_id") in {e["source_id"] for e in expected} for c in citations)
    locator_hits = sum(any(matches(e, c) for e in expected) for c in citations)
    coverage = sum(any(matches(e, r) for r in retrieved) for e in expected)
    refused = result["status"] == "declined"
    return {"scored": True, "citation_count": len(citations), "citation_source_hits": source_hits,
        "citation_locator_hits": locator_hits, "citation_source_accuracy": ratio(source_hits, len(citations)),
        "citation_locator_accuracy": ratio(locator_hits, len(citations)),
        "missing_citation": case.supported and not refused and not citations,
        "refusal_correct": refused == (not case.supported), "refused": refused,
        "retrieval_source_recall": float(coverage > 0) if case.supported else None,
        "evidence_coverage": ratio(coverage, len(expected))}


def aggregate(cases: list[Case], results: list[dict]) -> dict:
    by_id = {r["case_id"]: r for r in results}
    scored = [(c, case_metrics(c, by_id[c.case_id])) for c in cases if c.case_id in by_id]
    scored = [(c, m) for c, m in scored if m["scored"]]
    confusion = Counter({k: 0 for k in ("TP", "TN", "FP", "FN")})
    for c, m in scored:
        confusion[("T" if m["refusal_correct"] else "F") + ("P" if m["refused"] else "N")] += 1
    tp, tn, fp, fn = (confusion[k] for k in ("TP", "TN", "FP", "FN"))
    count = sum(m["citation_count"] for _, m in scored)
    metrics = {"cases_total": len(cases), "cases_scored": len(scored), "confusion": dict(confusion),
        "citation_count": count,
        "citation_source_accuracy": ratio(sum(m["citation_source_hits"] for _, m in scored), count),
        "citation_locator_accuracy": ratio(sum(m["citation_locator_hits"] for _, m in scored), count),
        "answers_missing_citations": sum(m["missing_citation"] for _, m in scored),
        "refusal_precision": ratio(tp, tp + fp), "refusal_recall": ratio(tp, tp + fn),
        "refusal_f1": ratio(2 * tp, 2 * tp + fp + fn), "refusal_accuracy": ratio(tp + tn, len(scored))}
    for key in ("retrieval_source_recall", "evidence_coverage"):
        values = [m[key] for _, m in scored if m[key] is not None]
        metrics[key] = mean(values) if values else None
    return metrics


def failures(case: Case, result: dict) -> list[dict]:
    m = case_metrics(case, result)
    reasons = []
    if not m["scored"]:
        reasons.append(("execution", result.get("error") or result["status"]))
    else:
        if not m["refusal_correct"]:
            reasons.append(("refusal", "supported query refused" if case.supported else "unsupported query answered"))
        if m["missing_citation"]:
            reasons.append(("citation", "answer has no citations"))
        for key, reason in [("citation_source_accuracy", "wrong source"), ("citation_locator_accuracy", "wrong source/page/slide/timestamp"),
                            ("retrieval_source_recall", "retrieval miss"), ("evidence_coverage", "incomplete expected evidence")]:
            if m.get(key) is not None and m[key] < 1:
                reasons.append((key, reason))
        for key, value in result.get("framework", {}).get("scores", {}).items():
            if value is not None and value < 1 - 1e-8:
                reasons.append((key, "framework score below 1; inspect raw evaluator judgments"))
        for key, raw in result.get("framework", {}).get("raw", {}).items():
            if raw.get("status") in {"error", "undefined"}:
                reasons.append((key, "framework metric unavailable: " + raw["status"]))
    return [{"case_id": case.case_id, "question": case.question, "expected": [e.model_dump() for e in case.expected],
        "retrieved": result["retrieved"], "answer": result.get("answer"), "status": result["status"],
        "citations": result["citations"], "failed_metric": key, "reason": reason} for key, reason in reasons]
