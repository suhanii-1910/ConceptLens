"""Counterfactual simulation. Latent truth lives here, outside every policy API."""
import asyncio
import hashlib
import json
import random
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from statistics import mean, stdev

from pydantic import Field, model_validator
from app.services.learner_mastery import compute_bkt_step
from .common import SIMULATION, digest
from .dataset import Strict
from .metrics import ratio
from .policy import POLICIES, DEFINITIONS, MemoryPolicy, baseline_action


class Profile(Strict):
    name: str
    target: float = Field(ge=0, le=1)
    prerequisite: float = Field(ge=0, le=1)
    procedural: float = Field(ge=0, le=1)
    misconception: bool
    noise: float = Field(ge=0, le=1)


class Config(Strict):
    version: str
    seeds: list[int] = Field(min_length=2)
    learners_per_profile_seed: int = Field(ge=1, le=1000)
    sessions: int = Field(ge=2)
    horizon: int = Field(ge=3, le=100)
    bootstrap_samples: int = Field(ge=100)
    bootstrap_seed: int
    guess: float = Field(ge=0, le=1)
    slip: float = Field(ge=0, le=1)
    misconception_penalty: float = Field(ge=0, le=1)
    misconception_repair_probability: float = Field(ge=0, le=1)
    reasoning_sensitivity: float = Field(ge=0, le=1)
    reasoning_false_positive: float = Field(ge=0, le=1)
    gains: dict[str, float]
    profiles: list[Profile] = Field(min_length=5)

    @model_validator(mode="after")
    def valid(self):
        if len(set(self.seeds)) != len(self.seeds) or len({p.name for p in self.profiles}) != len(self.profiles):
            raise ValueError("seeds and profile names must be unique")
        if self.guess + self.slip > 1 or any(not 0 <= v <= 1 for v in self.gains.values()):
            raise ValueError("invalid transition probabilities")
        required = {"source_explanation","visual_explanation","worked_example","prerequisite_recap","prerequisite_practice","general_practice","prerequisite_probe","diagnostic_probe","transfer_check"}
        if set(self.gains) != required:
            raise ValueError("gain table must cover exactly the documented actions")
        return self


@dataclass(frozen=True)
class Hidden:
    target: float
    prerequisite: float
    procedural: float
    misconception: bool
    noise: float


@dataclass(frozen=True)
class Observation:
    """The complete policy-visible entry observation. No hidden-state reference."""
    correct: bool
    reasoning_marker: bool


def uniform(key: tuple, event: str) -> float:
    # The policy name is deliberately absent from every random counter.
    raw = hashlib.sha256(json.dumps([*key, event], separators=(",", ":")).encode()).digest()
    return int.from_bytes(raw[:8], "big") / 2**64


def answer(state: Hidden, item: dict, config: Config, key: tuple) -> bool:
    mastery = getattr(state, item["concept"])
    if item["style"] == "procedural": mastery = (mastery + state.procedural) / 2
    probability = config.guess + (1-config.slip-config.guess) * mastery
    if state.misconception and item["concept"] == "target": probability -= config.misconception_penalty
    probability = (1-state.noise) * max(0, probability) + state.noise * config.guess
    return uniform(key, "answer") < probability


def transition(state: Hidden, action: str, config: Config, key: tuple) -> Hidden:
    """One shared learning model: no policy argument, no policy-specific bonus."""
    concept = "prerequisite" if action.startswith("prerequisite_") else "target"
    gain = config.gains.get(action, 0)
    if concept == "target": gain *= 0.35 + 0.65 * state.prerequisite
    old = getattr(state, concept)
    misconception = state.misconception
    if concept == "target" and gain > 0 and uniform(key, "repair") < config.misconception_repair_probability:
        misconception = False
    return replace(state, **{concept: old + (1-old)*gain}, misconception=misconception)


def observe(state: Hidden, correct: bool, config: Config, key: tuple) -> Observation:
    probability = config.reasoning_sensitivity if state.misconception else config.reasoning_false_positive
    return Observation(correct=correct, reasoning_marker=not correct and uniform(key, "reasoning") < probability)


def load_bank(path: Path, sessions: int) -> dict:
    bank = json.loads(path.read_text())
    items = bank["items"]
    for field in ("item_id", "question"):
        values = [" ".join(i[field].casefold().split()) if field == "question" else i[field] for i in items]
        if len(set(values)) != len(items): raise ValueError("duplicate bank " + field)
    if len([i for i in items if i["role"] == "heldout"]) < sessions:
        raise ValueError("each session requires a distinct held-out item; extend/version the bank")
    for i in items:
        if i["role"] not in {"training","heldout"} or i["concept"] not in {"target","prerequisite"} or i["style"] not in {"conceptual","procedural"}:
            raise ValueError("invalid bank category")
        if i["role"] == "heldout" and i["concept"] != "target":
            raise ValueError("held-out transfer must assess the common target")
        if len(i["options"]) != 4 or len(set(i["options"])) != 4 or type(i["correct_option_index"]) is not int or not 0 <= i["correct_option_index"] < 4:
            raise ValueError("invalid MCQ")
    if bank["prerequisite_edges"] != [["prerequisite", "target"]]:
        raise ValueError("benchmark requires its source-reviewed prerequisite graph")
    return bank


def repetition(items: list[dict]) -> dict:
    seen_id, seen_text, seen_template = set(), set(), set()
    exact = template = 0
    for item in items:
        text = " ".join(item["question"].casefold().split())
        exact += item["item_id"] in seen_id or text in seen_text
        template += item["template_id"] in seen_template
        seen_id.add(item["item_id"]); seen_text.add(text); seen_template.add(item["template_id"])
    return {"questions": len(items), "exact_repeats": exact, "template_repeats": template}


async def learner(policy: str, profile: Profile, seed: int, replica: int, config: Config, bank: dict) -> dict:
    state = Hidden(**profile.model_dump(exclude={"name"}))
    initial = asdict(state)
    bkt, counts = {"target":0.2,"prerequisite":0.2}, {"target":0,"prerequisite":0}
    all_items, sessions = [], []
    training = {c:[i for i in bank["items"] if i["role"]=="training" and i["concept"]==c] for c in bkt}
    heldout = [i for i in bank["items"] if i["role"]=="heldout"]
    for session_index in range(config.sessions):
        key = (seed,profile.name,replica,session_index)
        before = asdict(state)
        entry = training["target"][(session_index*2)%len(training["target"])]
        entry_correct = answer(state,entry,config,(*key,-1))
        obs = observe(state,entry_correct,config,(*key,-1))
        bkt["target"] = compute_bkt_step(bkt["target"],entry_correct).updated_mastery
        counts["target"] += 1
        all_items.append(entry)
        history, complete, diagnosis_status = [], False, None
        with MemoryPolicy(bank["items"],bkt,counts,session_index,bank["prerequisite_edges"]) as adapter:
            if policy == "CONCEPTLENS": await adapter.start(obs.reasoning_marker)
            for step in range(config.horizon):
                action = adapter.session.current_action if policy == "CONCEPTLENS" else baseline_action(policy,step,history,obs.correct)
                if action is None or action in {"complete","reconsider_diagnosis","collect_more_reasoning"}: break
                item = adapter.current_item() if policy == "CONCEPTLENS" else None
                if item is None and action in {"general_practice","transfer_check","prerequisite_practice","prerequisite_probe","diagnostic_probe"}:
                    concept = "prerequisite" if action.startswith("prerequisite") else "target"
                    item = training[concept][(session_index*2+step+2)%len(training[concept])]
                correct = answer(state,item,config,(*key,step)) if item else None
                if item: all_items.append(item)
                state = transition(state,action,config,(*key,step))
                understood = uniform((*key,step),"feedback") < (1-state.noise)*state.target + state.noise*0.5
                history.append({"step":step,"action":action,"item_id":item["item_id"] if item else None,
                                "correct":correct,"feedback":"understood" if understood else "still_confused"})
                if policy == "CONCEPTLENS" and action != "general_practice":
                    await adapter.respond(correct,understood)
                    complete = adapter.session.status == "complete"
                elif item:
                    # General-practice/ordinary assessments and transfer update BKT; prereq probes do not.
                    concept = item["concept"]
                    bkt[concept] = compute_bkt_step(bkt[concept],correct).updated_mastery
                    counts[concept] += 1
                    if action == "transfer_check": complete = correct
                if policy == "CONCEPTLENS" and action == "general_practice":
                    # Production safe action has no Phase 7 repair loop. One shared-bank ordinary practice,
                    # then stop; do not invent extra targeted repair for unconfirmed diagnoses.
                    break
            if policy == "CONCEPTLENS": diagnosis_status = adapter.diagnosis.status
            calls = list(adapter.calls) if policy == "CONCEPTLENS" else []
        transfer_item = heldout[session_index]
        success = answer(state,transfer_item,config,(*key,"heldout"))
        all_items.append(transfer_item)
        sessions.append({"session":session_index,"initial_latent":before,"final_latent":asdict(state),
            "observation":asdict(obs),"entry_item_id":entry["item_id"],"heldout_item_id":transfer_item["item_id"],
            "transfer_success":success,"interventions":len(history),"latent_gain":state.target-before["target"],
            "prerequisite_gain":state.prerequisite-before["prerequisite"],"completion":complete,
            "bkt_target":bkt["target"],"bkt_absolute_error":abs(bkt["target"]-state.target),
            "strategy_changes":sum(a["action"]!=b["action"] for a,b in zip(history,history[1:])),
            "diagnosis_status":diagnosis_status,"production_calls":calls,"trajectory":history})
    return {"learner_id":f"{seed}/{profile.name}/{replica}","policy":policy,"seed":seed,"profile":profile.name,
            "replica":replica,"initial_latent":initial,"final_latent":asdict(state),"sessions":sessions,
            "repetition":repetition(all_items)}


def totals(rows: list[dict]) -> dict:
    sessions = [s for r in rows for s in r["sessions"]]
    success = sum(s["transfer_success"] for s in sessions)
    return {"transfer_success":mean(s["transfer_success"] for s in sessions),
        "interventions_per_success":ratio(sum(s["interventions"] for s in sessions),success),
        "question_repetition":ratio(sum(r["repetition"]["exact_repeats"] for r in rows),sum(r["repetition"]["questions"] for r in rows)),
        "template_repetition":ratio(sum(r["repetition"]["template_repeats"] for r in rows),sum(r["repetition"]["questions"] for r in rows)),
        "latent_mastery_gain":mean(r["final_latent"]["target"]-r["initial_latent"]["target"] for r in rows),
        "session_completion":mean(s["completion"] for s in sessions),
        "bkt_absolute_error":mean(s["bkt_absolute_error"] for s in sessions),
        "strategy_changes":mean(s["strategy_changes"] for s in sessions),
        "prerequisite_mastery_gain":mean(r["final_latent"]["prerequisite"]-r["initial_latent"]["prerequisite"] for r in rows)}


def summarize(rows: list[dict], config: Config) -> dict:
    output = {}
    for policy in POLICIES:
        selected = [r for r in rows if r["policy"]==policy]
        values = totals(selected)
        # Stratify by profile, resample whole learners (all their sessions stay together).
        groups = [[r for r in selected if r["profile"]==p.name] for p in config.profiles]
        rng, samples = random.Random(config.bootstrap_seed), defaultdict(list)
        for _ in range(config.bootstrap_samples):
            sampled = [r for group in groups for r in rng.choices(group,k=len(group))]
            for metric,value in totals(sampled).items():
                if value is not None: samples[metric].append(value)
        stats = {}
        for metric,value in values.items():
            ordered = sorted(samples[metric])
            per_learner = [totals([r])[metric] for r in selected]
            finite = [v for v in per_learner if v is not None]
            stats[metric] = {"mean":value,"n_learners":len(selected),"n_sessions":sum(len(r["sessions"]) for r in selected),
                "sd_across_learners":stdev(finite) if len(finite)>1 else None,
                "sd_n_defined":len(finite),"ci95":[ordered[int(.025*(len(ordered)-1))],ordered[int(.975*(len(ordered)-1))]] if ordered else None,
                "bootstrap_defined":len(ordered)}
        output[policy] = stats
    return output


async def run(config: Config, bank: dict) -> dict:
    rows = []
    for seed in config.seeds:
        for profile in config.profiles:
            for replica in range(config.learners_per_profile_seed):
                for policy in POLICIES:
                    rows.append(await learner(policy,profile,seed,replica,config,bank))
    return {"label":SIMULATION,"configuration":config.model_dump(),"dataset_version":bank["version"],
            "policy_definitions":DEFINITIONS,"counts":{"independent_learners":len(rows)//3,"policy_learner_runs":len(rows),
            "sessions_per_policy":len(rows)//3*config.sessions,"profiles":len(config.profiles)},
            "statistics":summarize(rows,config),"by_profile":{p.name:{policy:totals([r for r in rows if r["profile"]==p.name and r["policy"]==policy]) for policy in POLICIES} for p in config.profiles},
            "learners":rows,
            "limitations":["Synthetic transition assumptions; not measured student learning.",
            "Frozen content and noisy reasoning fixtures do not evaluate live generator/verifier/diagnosis quality.",
            "Equal maximum horizon; policies may stop early. Held-out checks are common and never taught.",
            "Template repetition groups manually declared equivalent structures; no semantic embedding threshold.",
            "Confidence intervals condition on this simulator and five fixed profiles; no significance test."]}
