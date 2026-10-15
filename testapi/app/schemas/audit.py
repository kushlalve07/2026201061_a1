from __future__ import annotations

from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from app.schemas.bookings import AuditEntry
from app.schemas.common import Page


class AuditRow(AuditEntry):
    running_balance: float
    matches: bool


class AuditSummary(BaseModel):
    entries: int
    opening_balance: float | None
    credits_total: float
    credits_count: int
    debits_total: float
    debits_count: int
    closing_balance: float | None


class RiderBalance(BaseModel):
    id: UUID
    name: str
    wallet_balance: float


class WalletAudit(Page[AuditRow]):
    rider: RiderBalance
    date_from: date | None
    date_to: date | None
    order: Literal["asc", "desc"]
    summary: AuditSummary
