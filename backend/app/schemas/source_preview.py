from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SourceLocation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Literal['page','slide','time']
    number: int | None = Field(default=None, ge=1)
    start: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end: float | None = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode='after')
    def valid(self):
        if self.kind=='time':
            if self.start is None or self.number is not None or (self.end is not None and self.end<self.start):
                raise ValueError('Time locator requires ordered timestamps and no page/slide number')
        elif self.number is None or self.start is not None or self.end is not None:
            raise ValueError('Page/slide locator requires a number and no timestamp')
        return self
