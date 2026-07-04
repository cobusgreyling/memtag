from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class MemoryStatus(str, Enum):
    FACT = "fact"
    HYPOTHESIS = "hypothesis"
    DEPRECATED = "deprecated"


VALID_STATUSES = {s.value for s in MemoryStatus}
MEMTAG_VERSION = "1"


@dataclass
class MemoryMeta:
    path: Path
    memtag: str | None = None
    confidence: float | None = None
    status: str | None = None
    source: str | None = None
    created: date | None = None
    expires: date | None = None
    supersedes: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    body: str = ""
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)

    @property
    def is_memtagged(self) -> bool:
        return self.memtag is not None

    @property
    def is_expired(self) -> bool:
        if self.expires is None:
            return False
        return self.expires < date.today()

    @property
    def is_active(self) -> bool:
        if not self.is_memtagged:
            return True
        if self.status == MemoryStatus.DEPRECATED.value:
            return False
        return not self.is_expired

    @property
    def trust_score(self) -> float:
        if not self.is_memtagged:
            return 0.35
        base = self.confidence if self.confidence is not None else 0.5
        if self.status == MemoryStatus.FACT.value:
            base += 0.15
        elif self.status == MemoryStatus.HYPOTHESIS.value:
            base -= 0.1
        elif self.status == MemoryStatus.DEPRECATED.value:
            base = 0.0
        if self.is_expired:
            base *= 0.25
        if self.source and self.source.startswith("human:"):
            base += 0.1
        return max(0.0, min(1.0, base))


@dataclass
class LintIssue:
    severity: str
    code: str
    message: str
    path: Path
    related: Path | None = None


@dataclass
class LintReport:
    issues: list[LintIssue] = field(default_factory=list)
    scanned: int = 0
    memtagged: int = 0

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


@dataclass
class PackResult:
    selected: list[MemoryMeta]
    budget: int
    used_tokens: int
    skipped_expired: int
    skipped_deprecated: int


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    raise ValueError(f"invalid date: {value!r}")