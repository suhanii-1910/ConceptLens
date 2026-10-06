"""Executed only by the isolated, pinned RAGAS interpreter. JSON in / JSON out."""
import asyncio
import importlib.metadata
import json
import math
import os
import sys

os.environ["RAGAS_DO_NOT_TRACK"] = "true"
from ragas.llms.base import InstructorBaseRagasLLM
from ragas.embeddings.base import BaseRagasEmbedding, embedding_factory
from ragas.metrics.collections import Faithfulness, AnswerRelevancy, ContextPrecisionWithReference, ContextRecall


class FixtureLLM(InstructorBaseRagasLLM):
    """Deterministic structured evaluator outputs; actual RAGAS computes the scores."""
    def __init__(self, question, verdict):
        self.question, self.verdict = question, verdict

    def generate(self, prompt, response_model):
        v = self.verdict
        outputs = {
            "StatementGeneratorOutput": {"statements": ["fixture claim"]},
            "NLIStatementOutput": {"statements": [{"statement": "fixture claim", "reason": "fixture", "verdict": v}]},
            "AnswerRelevanceOutput": {"question": self.question, "noncommittal": 1 - v},
            "ContextPrecisionOutput": {"verdict": v, "reason": "fixture"},
            "ContextRecallOutput": {"classifications": [{"statement": "fixture claim", "reason": "fixture", "attributed": v}]}}
        return response_model.model_validate(outputs[response_model.__name__])

    async def agenerate(self, prompt, response_model):
        return self.generate(prompt, response_model)


class FixtureEmbedding(BaseRagasEmbedding):
    def embed_text(self, text, **kwargs):
        return [1.0, 0.0, 0.0]

    async def aembed_text(self, text, **kwargs):
        return self.embed_text(text)


class RecordingLLM(InstructorBaseRagasLLM):
    def __init__(self, delegate):
        self.delegate, self.records = delegate, []

    def generate(self, prompt, response_model):
        result = self.delegate.generate(prompt, response_model)
        self.records.append({"schema": response_model.__name__, "judgment": result.model_dump(mode="json")})
        return result

    async def agenerate(self, prompt, response_model):
        result = await self.delegate.agenerate(prompt, response_model)
        self.records.append({"schema": response_model.__name__, "judgment": result.model_dump(mode="json")})
        return result


async def evaluate(request):
    if importlib.metadata.version("ragas") != "0.4.3":
        raise RuntimeError("RAGAS version differs from frozen benchmark")
    sample = request["sample"]
    if request["fixture"]:
        llm = FixtureLLM(sample["user_input"], request["fixture_verdict"])
        embeddings = FixtureEmbedding()
    else:
        from openai import AsyncOpenAI
        from ragas.llms import llm_factory
        client = AsyncOpenAI(base_url=os.environ["CONCEPTLENS_EVAL_BASE_URL"],
                             api_key=os.environ["CONCEPTLENS_EVAL_API_KEY"], timeout=60, max_retries=1)
        llm = llm_factory(os.environ["CONCEPTLENS_EVAL_MODEL"], client=client)
        embeddings = embedding_factory("openai", model=os.environ["CONCEPTLENS_EVAL_EMBEDDING_MODEL"],
                                       client=client, interface="modern")
    llm = RecordingLLM(llm)
    metrics = [("faithfulness", Faithfulness(llm=llm), ("user_input", "response", "retrieved_contexts")),
               ("answer_relevancy", AnswerRelevancy(llm=llm, embeddings=embeddings), ("user_input", "response")),
               ("context_precision", ContextPrecisionWithReference(llm=llm), ("user_input", "reference", "retrieved_contexts")),
               ("context_recall", ContextRecall(llm=llm), ("user_input", "reference", "retrieved_contexts"))]
    scores, raw = {}, {}
    for name, metric, keys in metrics:
        llm.records.clear()
        try:
            result = await metric.ascore(**{k: sample[k] for k in keys})
            value = float(result.value)
            scores[name] = value if math.isfinite(value) else None
            raw[name] = {"implementation": type(metric).__module__ + "." + type(metric).__name__,
                         "status": "scored" if scores[name] is not None else "undefined",
                         "value": scores[name], "judgments": list(llm.records)}
        except Exception as exc:
            scores[name] = None
            raw[name] = {"status": "error", "error_type": type(exc).__name__, "judgments": list(llm.records)}
    return {"label": "TEST FIXTURE — NOT A SUBMISSION RESULT" if request["fixture"] else "REAL EVALUATION RESULT",
            "framework": "ragas", "version": "0.4.3", "status": "scored" if all(v is not None for v in scores.values()) else "partial",
            "scores": scores, "raw": raw}


if __name__ == "__main__":
    print(json.dumps(asyncio.run(evaluate(json.load(sys.stdin))), allow_nan=False))
