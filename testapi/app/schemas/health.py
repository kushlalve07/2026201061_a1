from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

State = Literal["ok", "down"]


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    postgres: State
    mongo: State
