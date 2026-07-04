from __future__ import annotations

from pathlib import Path

from memtag.models import MEMTAG_VERSION, VALID_STATUSES, LintIssue, LintReport, MemoryMeta
from memtag.vault import load_vault, resolve_supersedes_target


def lint_vault(vault: Path) -> LintReport:
    notes = load_vault(vault)
    report = LintReport(scanned=len(notes), memtagged=sum(1 for n in notes if n.is_memtagged))

    by_stem: dict[str, list[MemoryMeta]] = {}
    for note in notes:
        by_stem.setdefault(note.path.stem.lower(), []).append(note)

    for note in notes:
        if not note.is_memtagged:
            continue

        if note.memtag != MEMTAG_VERSION:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="MEMTAG_VERSION",
                    message=f"expected memtag '{MEMTAG_VERSION}', got '{note.memtag}'",
                    path=note.path,
                )
            )

        if note.confidence is None:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="MISSING_CONFIDENCE",
                    message="memtagged note missing confidence (0.0–1.0)",
                    path=note.path,
                )
            )
        elif not 0.0 <= note.confidence <= 1.0:
            report.issues.append(
                LintIssue(
                    severity="error",
                    code="INVALID_CONFIDENCE",
                    message=f"confidence must be between 0 and 1, got {note.confidence}",
                    path=note.path,
                )
            )

        if note.status is None:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="MISSING_STATUS",
                    message="memtagged note missing status (fact|hypothesis|deprecated)",
                    path=note.path,
                )
            )
        elif note.status not in VALID_STATUSES:
            report.issues.append(
                LintIssue(
                    severity="error",
                    code="INVALID_STATUS",
                    message=f"unknown status '{note.status}'",
                    path=note.path,
                )
            )

        if note.source is None:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="MISSING_SOURCE",
                    message="memtagged note missing source (human:* or agent:*)",
                    path=note.path,
                )
            )

        if note.is_expired and note.status != "deprecated":
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="EXPIRED",
                    message=f"note expired on {note.expires}",
                    path=note.path,
                )
            )

        for link in note.supersedes:
            target = resolve_supersedes_target(vault, link)
            if target is None:
                report.issues.append(
                    LintIssue(
                        severity="warning",
                        code="ORPHAN_SUPERSEDES",
                        message=f"supersedes link not found: {link}",
                        path=note.path,
                    )
                )

    _detect_contradictions(notes, report)
    return report


def _detect_contradictions(notes: list[MemoryMeta], report: LintReport) -> None:
    active = [n for n in notes if n.is_memtagged and n.is_active and n.tags]
    for i, left in enumerate(active):
        for right in active[i + 1 :]:
            shared = set(left.tags) & set(right.tags)
            if not shared:
                continue
            if left.body.strip().lower() == right.body.strip().lower():
                continue
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="POSSIBLE_CONTRADICTION",
                    message=(
                        f"active notes share tag(s) {sorted(shared)} but differ in content "
                        f"({left.path.name} vs {right.path.name})"
                    ),
                    path=left.path,
                    related=right.path,
                )
            )