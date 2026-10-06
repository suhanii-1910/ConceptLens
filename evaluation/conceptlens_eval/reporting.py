"""Deterministic JSON/CSV/Markdown/SVG reporting with mandatory provenance labels."""
import csv
import html
import json
from collections import Counter
from pathlib import Path
from .common import REAL, SIMULATION, FIXTURE, PENDING, write_json


def fmt(value):
    return "PENDING / undefined" if value is None else f"{value:.4f}" if isinstance(value,(float,int)) else str(value)


def table(headers, rows):
    def cell(v): return str(v).replace("|","\\|").replace("\n"," ")
    return "\n".join(["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |",
                      *["| " + " | ".join(cell(c) for c in row) + " |" for row in rows]])


def write_csv(path: Path, rows: list[dict], fields: list[str]):
    with path.open("w",newline="") as f:
        writer = csv.DictWriter(f,fieldnames=fields,extrasaction="ignore",lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in row.items()})


def chart(path: Path, title: str, label: str, values: dict, *, maximum=None):
    height = 105 + max(1,len(values))*42
    valid = [v for v in values.values() if v is not None]
    scale = maximum or max(valid,default=1) or 1
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="{height}" viewBox="0 0 960 {height}" role="img" aria-label="{html.escape(title)}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Arial,sans-serif;font-size:13px;fill:#18263a}.title{font-size:19px;font-weight:bold}</style>',
        f'<text x="20" y="27" class="title">{html.escape(title)}</text>',f'<text x="20" y="51">{html.escape(label)}</text>']
    for i,(name,value) in enumerate(values.items()):
        y = 80 + i*42
        parts.append(f'<text x="20" y="{y+16}">{html.escape(name)}</text>')
        if value is not None:
            parts.append(f'<rect x="300" y="{y}" width="{max(0,value)/scale*440:.2f}" height="24" fill="#3168a0"/>')
        parts.append(f'<text x="760" y="{y+16}">{html.escape(fmt(value))}</text>')
    parts.append(f'<text x="300" y="{height-10}">Bars start at 0; scale maximum {scale:.4g}. Null values have no bar.</text></svg>')
    path.write_text("\n".join(parts)+"\n")


def build_report(grounding: dict, simulation: dict, output: Path) -> dict:
    g, s = grounding["payload"], simulation["payload"]
    if g["label"] not in {REAL,PENDING,FIXTURE} or s["label"] not in {SIMULATION,FIXTURE}:
        raise ValueError("missing/invalid result provenance label")
    fixture = FIXTURE in {g["label"],s["label"]}
    # Never mix fixture scores into a submission-looking directory/report.
    if fixture and "fixture" not in output.name.lower():
        raise ValueError("fixture report requires a directory explicitly named fixture")
    output.mkdir(parents=True,exist_ok=True)
    title = FIXTURE if fixture else "ConceptLens Phase 9 evaluation"
    stats = {p:s["statistics"][p] for p in ("FIXED", "SIMPLE ADAPTIVE", "CONCEPTLENS")}
    comparison = []
    for policy,metrics in stats.items():
        transfer = metrics["transfer_success"]
        comparison.append([policy,fmt(transfer["mean"]),str(transfer["ci95"]),transfer["n_learners"],transfer["n_sessions"],
            fmt(metrics["interventions_per_success"]["mean"]),fmt(metrics["question_repetition"]["mean"]),
            fmt(metrics["latent_mastery_gain"]["mean"]),fmt(metrics["session_completion"]["mean"])])
    pending = g["label"]==PENDING
    framework_status = "REAL FRAMEWORK RESULTS: PENDING PROVIDER CONFIGURATION" if pending or not any(m["n"] for m in g["framework_metrics"].values()) else "Conditional on supported, answered, evaluable cases; inspect metric N."
    observed_failures = [f for f in g["failures"] if f["status"] != "pending"]
    handoff = {"phase":"10 (not implemented)","grounding_status":g["label"],"simulation_status":s["label"],"priorities":[
        {"rank":1,"weakness":"Real grounding quality remains unmeasured without generator/evaluator configuration.","evidence":{"framework_scored_cases":max((m["n"] for m in g["framework_metrics"].values()),default=0)},"reserved_work":"Complete provider-backed Track-D closure on frozen test split; preserve failures."},
        {"rank":2,"weakness":"Diagram labels are raster-only; current retrieval lacks true visual semantics.","evidence":{"figure_cases":g["by_modality"].get("figure",{}),"measured_failure_rate":None if pending else "inspect per-case failures"},"reserved_work":"True visual/diagram evidence and exact source opening; citations alone are not semantic proof."},
        {"rank":3,"weakness":"Unconfirmed diagnoses expose a limited cold-start/general-practice path.","evidence":{"simulated_transfer_success":{p:v["transfer_success"]["mean"] for p,v in stats.items()},"scope":"synthetic profiles and frozen diagnostic fixtures only"},"reserved_work":"Stronger cold-start diagnostic, justified by a real follow-up study before educational claims."},
        {"rank":4,"weakness":"MCQ-only simulated assessments cannot validate generated reasoning or numerical solutions.","evidence":{"assessment_format":"multiple_choice","live_verifier_evaluated":False},"reserved_work":"Short-answer and numerical assessment; deterministic CPU-scheduling verifier."},
        {"rank":5,"weakness":"BKT estimates are distinct from latent ability; current evidence does not establish real learner calibration.","evidence":{"simulated_bkt_mae":{p:v["bkt_absolute_error"]["mean"] for p,v in stats.items()}},"reserved_work":"Post-assessment weak-topic reporting; expose evidence and uncertainty; real learner validation."}]}
    lines = [f"# {title}","", "## What was evaluated?", "",
        "The actual ingestion/retrieval/Ask pipeline is executable against a disposable PostgreSQL database. RAGAS 0.4.3 supplies four framework metrics; deterministic source/location/refusal metrics are separate.","",
        f"Grounding: **{g['label']}**. Dataset `{g['dataset_version']}`, split `{g['split']}`, {g['custom_metrics']['cases_total']} cases.",
        "",f"**{framework_status}**", "No pending value is a zero, a success, or a test-fixture score.","",
        table(["Framework metric","Mean","Scored N"],[[k,fmt(v["mean"]),v["n"]] for k,v in g["framework_metrics"].items()]),"",
        table(["Custom metric","Value"],[[k,fmt(v)] for k,v in g["custom_metrics"].items() if k != "confusion"]),"",
        "Refusal confusion matrix: `"+json.dumps(g["custom_metrics"]["confusion"],sort_keys=True)+"`.","",
        "## Grounding by modality", "",
        table(["Modality","Cases","Scored","Locator accuracy","Evidence coverage"],[[m,v["cases_total"],v["cases_scored"],fmt(v["citation_locator_accuracy"]),fmt(v["evidence_coverage"])] for m,v in g["by_modality"].items()]),"",
        table(["Modality", "Faithfulness (N)", "Relevancy (N)", "Context precision (N)", "Context recall (N)"],
              [[m, *[f"{fmt(v['framework_metrics'][k]['mean'])} ({v['framework_metrics'][k]['n']})"
                       for k in ("faithfulness", "answer_relevancy", "context_precision", "context_recall")]]
               for m,v in g["by_modality"].items()]), "",
        "## Inspectable grounding failures", "",
        "No observed grounding failures or successes are claimed for pending cases. `grounding-cases.csv` preserves every pending case; `failures.csv` includes execution/pending reasons and complete source/answer/citation fields.","",
        table(["Case","Question","Failed metric","Reason"],[[f["case_id"],f["question"],f["failed_metric"],f["reason"]] for f in observed_failures[:20]]) if observed_failures else "No completed pipeline results are available to analyze." if pending else "No observed failures; inspect case counts and metric applicability.","",
        "## Policy comparison — SIMULATION", "",f"**{s['label']}**", "",
        "Five explicit profiles, identical starting states and counter-based random seeds, common item pool, four sessions and equal maximum action horizons. The held-out transfer check is never used in teaching. Production Phase 6/7 decisions run with frozen content and memory persistence; this does not test live LLM diagnosis or content verification.","",
        table(["Policy","Transfer success","95% CI","Learners","Sessions","Actions/success","Exact repetition","Latent gain","Internal completion"],comparison),"",
        "Latent gain is final minus initial simulated target mastery across all sessions. Internal completion means a policy's own verification passed; held-out transfer is the primary common outcome. Full metric N, learner SD, confidence intervals and profile breakdowns are in JSON/CSV.","",
        "The results do not establish that ConceptLens outperforms the baselines. The production safe path can end after general practice when diagnosis is unconfirmed. No test of statistical significance or real educational gain is claimed.","",
        "95% percentile bootstrap intervals resample whole learners within each fixed profile; sessions are not treated as independent participants. Policies use matched learner identities and random counters. The SD for efficiency describes defined per-learner ratios; the overall estimate is a ratio of totals.","",
        "## Limitations and Phase 10", "", *["- "+v for v in s["limitations"]],
        "- Small original authored corpus; reference locations measure location coverage, not entailment of every fact.",
        "- Page-level retrieval can find a figure caption without understanding its raster diagram. Framework judgments and case inspection are still necessary.",
        "- Exact source opening, real visual evidence, short-answer/numerical grading, CPU verifier, cold start and post-assessment reporting remain Phase 10.","",
        "See `phase10-handoff.json` for five ranked weaknesses, evidence and reserved work.","",
        "## Reproduction", "", "See `evaluation/README.md` for exact commands, provider configuration, metric definitions and database safeguards. JSON envelopes record commit, evaluation code hashes, configuration, dataset version and timestamps. Timestamp metadata is excluded from deterministic payload comparisons.",""]
    (output/"report.md").write_text("\n".join(lines))
    write_json(output/"phase10-handoff.json",handoff)
    write_json(output/"summary.json",{"grounding_label":g["label"],"simulation_label":s["label"],"framework":g["framework_metrics"],"custom":g["custom_metrics"],"simulation":stats})
    write_csv(output/"grounding-cases.csv",[{**r,"label":g["label"]} for r in g["cases"]],["label","case_id","query","split","case_type","modality","expected_supported","expected","reference_answer","status","answer","citations","retrieved","framework","custom","error","latency_seconds"])
    write_csv(output/"failures.csv",[{**f,"label":g["label"]} for f in g["failures"]],["label","case_id","question","expected","retrieved","answer","status","citations","failed_metric","reason"])
    write_csv(output/"simulation-summary.csv",[{"label":s["label"],"policy":p,"metric":m,**v} for p,metrics in stats.items() for m,v in metrics.items()],
              ["label","policy","metric","mean","n_learners","n_sessions","sd_across_learners","sd_n_defined","ci95","bootstrap_defined"])
    write_csv(output/"simulation-sessions.csv",[{"label":s["label"],"learner_id":r["learner_id"],"policy":r["policy"],"profile":r["profile"],**session} for r in s["learners"] for session in r["sessions"]],
              ["label","learner_id","policy","profile","session","heldout_item_id","transfer_success","interventions","latent_gain","prerequisite_gain","completion","bkt_target","bkt_absolute_error","diagnosis_status","strategy_changes","trajectory"])
    chart(output/"grounding-summary.svg","Grounding framework metrics",g["label"],{k:v["mean"] for k,v in g["framework_metrics"].items()},maximum=1)
    chart(output/"grounding-modality.svg","Expected evidence location coverage by modality",g["label"],{k:v["evidence_coverage"] for k,v in g["by_modality"].items()},maximum=1)
    counts = Counter(f["reason"] for f in observed_failures)
    chart(output/"failure-categories.svg","Observed grounding failure categories",g["label"],dict(counts) or {"No completed failures to count":None})
    for metric,name,title in [("transfer_success","transfer-success","Held-out transfer success"),("interventions_per_success","intervention-efficiency","Actions per successful held-out transfer"),("question_repetition","question-repetition","Exact question ID / normalized text repetition")]:
        chart(output/(name+".svg"),title,s["label"],{p:v[metric]["mean"] for p,v in stats.items()},maximum=1 if metric!="interventions_per_success" else None)
    return {"report":str(output/"report.md"),"grounding_label":g["label"],"simulation_label":s["label"]}
