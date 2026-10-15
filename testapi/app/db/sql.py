"""Tiny helpers for building parameterised WHERE clauses safely.

Only fixed SQL fragments written in code are ever concatenated; every user
value goes through a bound parameter.
"""
from __future__ import annotations

from typing import Any


class Filters:
    def __init__(self) -> None:
        self._clauses: list[str] = []
        self.params: dict[str, Any] = {}

    def add(self, clause: str, **params: Any) -> "Filters":
        self._clauses.append(clause)
        self.params.update(params)
        return self

    @property
    def where(self) -> str:
        return ("WHERE " + " AND ".join(self._clauses)) if self._clauses else ""


def like_pattern(text: str) -> str:
    """Substring pattern for ILIKE with the user's own % and _ treated literally."""
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
