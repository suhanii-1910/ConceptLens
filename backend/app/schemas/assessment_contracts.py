"""Private verified grading contracts; public questions never include these models."""
from fractions import Fraction
import re
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator
from app.schemas.scheduling import SchedulingInput


def number(value:str)->Fraction:
    if len(value)>80 or not re.fullmatch(r'[+-]?(?:[0-9]+/[0-9]+|[0-9]+(?:\.[0-9]*)?|\.[0-9]+)', value.strip()):
        raise ValueError('Enter a finite decimal, integer or fraction')
    try: result=Fraction(value.strip())
    except (ValueError,ZeroDivisionError,OverflowError):raise ValueError('Enter a finite decimal, integer or fraction') from None
    if abs(result)>10**15 or result.denominator>10**15:raise ValueError('Number exceeds supported precision/range')
    return result


class SchedulingTarget(BaseModel):
    model_config=ConfigDict(extra='forbid')
    scenario: SchedulingInput
    metric: Literal['completion','turnaround','waiting','response']
    pid: str|None=None


class GradingContract(BaseModel):
    model_config=ConfigDict(extra='forbid')
    reference_answer: str=Field(min_length=1,max_length=4000)
    required_facts: list[str]=Field(default_factory=list,max_length=20)
    expected_value: str|None=Field(default=None,max_length=80)
    tolerance: str='0'
    tolerance_reason: str|None=None
    integer_only: bool=False
    unit: str|None=Field(default=None,max_length=32,pattern=r'^[A-Za-z%][A-Za-z0-9 /%^-]*$')
    scheduling: SchedulingTarget|None=None

    @model_validator(mode='after')
    def valid(self):
        tolerance=number(self.tolerance)
        if tolerance<0 or (tolerance and not self.tolerance_reason):raise ValueError('Tolerance must be nonnegative and justified')
        if self.integer_only and tolerance:raise ValueError('Integer scheduling quantities require exact comparison')
        if self.expected_value is not None:
            expected=number(self.expected_value)
            if self.integer_only and expected.denominator!=1:raise ValueError('Expected value must be an integer')
        if any(not f.strip() for f in self.required_facts):raise ValueError('Required facts cannot be blank')
        return self


class SemanticGrade(BaseModel):
    model_config=ConfigDict(extra='forbid')
    verdict: Literal['correct','incorrect','cannot_grade']
    explanation: str=Field(min_length=1,max_length=3000)
    missing_facts: list[str]=Field(default_factory=list,max_length=20)
    source_supported: bool=Field(strict=True)
