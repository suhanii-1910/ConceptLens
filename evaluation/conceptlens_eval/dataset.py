"""Strict, portable source references. Database UUIDs are resolved only at runtime."""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .common import digest


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Locator(Strict):
    kind: Literal["page", "slide", "time"]
    number: int | None = Field(default=None, ge=1)
    start: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="after")
    def valid(self):
        if self.kind == "time":
            if self.number is not None or self.start is None or self.end is None or self.end < self.start:
                raise ValueError("time requires finite ordered start/end, no number")
        elif self.number is None or self.start is not None or self.end is not None:
            raise ValueError("page/slide requires only a positive number")
        return self


class Source(Strict):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    filename: str = Field(min_length=1)
    path: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    kind: Literal["pdf", "pptx", "video"]

    @model_validator(mode="after")
    def portable(self):
        if Path(self.filename).name != self.filename or Path(self.path).is_absolute() or ".." in Path(self.path).parts:
            raise ValueError("source must use a relative, contained path and plain filename")
        if Path(self.path).name != self.filename:
            raise ValueError("source filename must match path")
        return self


class Expected(Strict):
    source_id: str
    locator: Locator


class Case(Strict):
    case_id: str = Field(pattern=r"^[a-z][a-z0-9_-]+$")
    split: Literal["development", "test"]
    question: str = Field(min_length=5)
    case_type: Literal["text", "table_numerical", "video", "cross_source", "unsupported", "figure_diagram"]
    modality: Literal["text", "table", "video", "mixed", "figure", "none"]
    supported: bool
    expected: list[Expected]
    reference_answer: str
    required_facts: list[str]
    topic: str
    notes: str

    @model_validator(mode="after")
    def coherent(self):
        if self.supported and (not self.expected or not self.reference_answer.strip() or not self.required_facts):
            raise ValueError("supported cases require locators and reference facts")
        if not self.supported and (self.expected or self.required_facts or self.case_type != "unsupported"):
            raise ValueError("unsupported cases cannot contain expected citations/facts")
        if self.supported and self.case_type == "unsupported":
            raise ValueError("unsupported case_type cannot be supported")
        if len({e.model_dump_json() for e in self.expected}) != len(self.expected):
            raise ValueError("duplicate expected evidence")
        if self.case_type == "cross_source" and len({e.source_id for e in self.expected}) < 2:
            raise ValueError("cross-source requires distinct sources")
        modalities = dict(text="text", table_numerical="table", video="video", cross_source="mixed",
                          unsupported="none", figure_diagram="figure")
        if self.modality != modalities[self.case_type]:
            raise ValueError("case type and modality disagree")
        return self


class Manifest(Strict):
    version: str
    description: str
    frozen_at: str
    sources: list[Source] = Field(min_length=1)
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def references(self):
        for field, values in [("case IDs", [c.case_id for c in self.cases]),
                              ("source IDs", [s.source_id for s in self.sources]),
                              ("source filenames", [s.filename for s in self.sources]),
                              ("source paths", [s.path for s in self.sources])]:
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate/ambiguous {field}")
        sources = {s.source_id: s for s in self.sources}
        for case in self.cases:
            for expected in case.expected:
                if expected.source_id not in sources:
                    raise ValueError("unknown source reference")
                kind = sources[expected.source_id].kind
                if expected.locator.kind != {"pdf": "page", "pptx": "slide", "video": "time"}[kind]:
                    raise ValueError("locator incompatible with source type")
        return self


def load_manifest(path: Path, *, verify_files: bool = True) -> Manifest:
    manifest = Manifest.model_validate(json.loads(path.read_text()))
    if verify_files:
        for source in manifest.sources:
            asset = (path.parent / source.path).resolve()
            if not asset.is_relative_to(path.parent.resolve()) or not asset.is_file() or digest(asset) != source.sha256:
                raise ValueError(f"missing, escaped, or changed source: {source.source_id}")
    return manifest


def resolve_source(source: Source, records: list[dict]) -> dict:
    matches = [r for r in records if r["filename"] == source.filename and r["sha256"] == source.sha256]
    if len(matches) != 1:
        raise ValueError(f"source resolution requires exactly one match: {source.source_id}")
    return matches[0]
