"""Strict scheduling input: nonnegative integer arrival ticks, positive burst ticks."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Process(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    pid: str = Field(pattern=r'^[A-Za-z0-9_-]{1,32}$')
    arrival: int = Field(ge=0, le=1_000_000)
    burst: int = Field(gt=0, le=100_000)
    priority: int | None = Field(default=None, ge=0, le=1_000_000)


class SchedulingInput(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    algorithm: Literal['fcfs', 'sjf', 'srtf', 'priority', 'priority_preemptive', 'round_robin']
    processes: list[Process] = Field(min_length=1, max_length=100)
    quantum: int | None = Field(default=None, gt=0, le=100_000)

    @model_validator(mode='after')
    def validate_workload(self):
        if len({p.pid for p in self.processes}) != len(self.processes):
            raise ValueError('Process IDs must be unique')
        if sum(p.burst for p in self.processes) > 100_000:
            raise ValueError('Total burst exceeds the bounded solver workload')
        if self.algorithm.startswith('priority') and any(p.priority is None for p in self.processes):
            raise ValueError('Priority algorithms require a priority for every process')
        if (self.algorithm == 'round_robin') != (self.quantum is not None):
            raise ValueError('A quantum is required only for Round Robin')
        return self
