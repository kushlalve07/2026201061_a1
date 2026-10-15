"""Server-side paging: every list endpoint takes page/page_size and returns a total."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Query

MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class PageParams:
    page: int = 1
    page_size: int = 25

    @property
    def limit(self) -> int:
        return self.page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def wrap(self, items: list, total: int) -> dict:
        return {"items": items, "page": self.page, "page_size": self.page_size, "total": total}


def page_params(
    page: int = Query(1, ge=1, description="1-based page number"),
    page_size: int = Query(25, ge=1, le=MAX_PAGE_SIZE, description=f"rows per page (max {MAX_PAGE_SIZE})"),
) -> PageParams:
    return PageParams(page=page, page_size=page_size)
