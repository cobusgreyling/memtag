from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from memtag.models import (
    MEMTAG_VERSION,
    VALID_STATUSES,
    LintIssue,
    LintReport,
    MemoryMeta,
    MemoryStatus,
)
from memtag.parser import _normalize_contradicted_by, render_frontmatter
from memtag.trust import _find_contradictions, enrich_vault
from memtag.vault import load_vault, resolve_supersedes_target

_TRUST_TOLERANCE = 0.001


@dataclass
class _DerivedSnapshot:
    trust: float | None
    last_confirmed: object
    contradicted_by: list[str]


def _snapshot_derived(note: MemoryMeta) -> _DerivedSnapshot | None:
    raw = note.raw_frontmatter
    has_derived = any(key in raw for key in ("trust", "last_confirmed", "contradicted_by"))
    if not has_derived:
        return None
    trust = float(raw["trust"]) if raw.get("trust") is not None else None
    return _DerivedSnapshot(
        trust=trust,
        last_confirmed=raw.get("last_confirmed"),
        contradicted_by=_normalize_contradicted_by(raw.get("contradicted_by")),
    )


def lint_vault(
    vault: Path,
    *,
    write: bool = False,
    detect_tag_contradictions: bool = False,
) -> LintReport:
    notes = load_vault(vault)
    snapshots = {
        note.path: snapshot
        for note in notes
        if note.is_memtagged and (snapshot := _snapshot_derived(note)) is not None
    }
    enrich_vault(notes, vault, detect_tag_contradictions=detect_tag_contradictions)
    report = LintReport(scanned=len(notes), memtagged=sum(1 for n in notes if n.is_memtagged))

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

        if note.status == MemoryStatus.HYPOTHESIS.value and note.expires is None:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="MISSING_EXPIRES",
                    message="hypothesis notes should set expires",
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

        if note.is_superseded and note.is_active:
            report.issues.append(
                LintIssue(
                    severity="warning",
                    code="SUPERSEDED",
                    message="note is superseded by a newer active note",
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

        _report_derived_tampering(note, snapshots.get(note.path), report)

    _report_contradictions(notes, vault, report, detect_tag_contradictions)

    if write:
        for note in notes:
            if not note.is_memtagged:
                continue
            note.path.write_text(render_frontmatter(note), encoding="utf-8")
            report.written += 1

    return report


def _report_derived_tampering(
    note: MemoryMeta,
    snapshot: _DerivedSnapshot | None,
    report: LintReport,
) -> None:
    if snapshot is None:
        return

    mismatches: list[str] = []
    if (
        snapshot.trust is not None
        and note.trust is not None
        and abs(snapshot.trust - note.trust) > _TRUST_TOLERANCE
    ):
        mismatches.append("trust")

    if snapshot.last_confirmed is not None:
        expected = note.last_confirmed.isoformat() if note.last_confirmed else None
        persisted = str(snapshot.last_confirmed)[:10]
        if expected != persisted:
            mismatches.append("last_confirmed")

    if snapshot.contradicted_by != note.contradicted_by:
        mismatches.append("contradicted_by")

    if mismatches:
        report.issues.append(
            LintIssue(
                severity="error",
                code="DERIVED_TAMPERED",
                message=(
                    "derived fields do not match recomputed values "
                    f"({', '.join(mismatches)}); run lint --write"
                ),
                path=note.path,
            )
        )


def _report_contradictions(
    notes: list[MemoryMeta],
    vault: Path,
    report: LintReport,
    detect_tag_contradictions: bool,
) -> None:
    for left, right in _find_contradictions(
        notes,
        vault,
        detect_tag_contradictions=detect_tag_contradictions,
    ):
        report.issues.append(
            LintIssue(
                severity="warning",
                code="POSSIBLE_CONTRADICTION",
                message=(
                    f"active notes conflict in content "
                    f"({left.path.name} vs {right.path.name})"
                ),
                path=left.path,
                related=right.path,
            )
        )
