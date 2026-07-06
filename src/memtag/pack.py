from __future__ import annotations

import re
from pathlib import Path

from memtag.models import MemoryMeta, PackResult
from memtag.parser import TokenEstimator, estimate_tokens, render_frontmatter
from memtag.trust import enrich_vault
from memtag.vault import load_vault

TOKEN_RE = re.compile(r"[a-z0-9]+")


def _task_terms(task: str) -> set[str]:
    return set(TOKEN_RE.findall(task.lower()))


def _relevance(note: MemoryMeta, terms: set[str]) -> float:
    if not terms:
        return 0.5
    haystack = " ".join(
        [
            note.path.stem,
            note.body,
            " ".join(note.tags),
            note.source or "",
            note.subject or "",
        ]
    ).lower()
    note_terms = set(TOKEN_RE.findall(haystack))
    if not note_terms:
        return 0.0
    overlap = len(terms & note_terms)
    return overlap / max(len(terms), 1)


def _render_note(note: MemoryMeta) -> str:
    if note.is_memtagged:
        return render_frontmatter(note)
    return f"# {note.path.stem}\n\n{note.body}\n"


def _truncate_note(note: MemoryMeta, max_tokens: int) -> MemoryMeta:
    if max_tokens <= 0:
        return MemoryMeta(
            path=note.path,
            memtag=note.memtag,
            confidence=note.confidence,
            status=note.status,
            source=note.source,
            created=note.created,
            expires=note.expires,
            supersedes=list(note.supersedes),
            tags=list(note.tags),
            subject=note.subject,
            body="",
            raw_frontmatter=dict(note.raw_frontmatter),
            trust=note.trust,
            last_confirmed=note.last_confirmed,
            contradicted_by=list(note.contradicted_by),
            is_superseded=note.is_superseded,
        )
    char_budget = max_tokens * 4
    return MemoryMeta(
        path=note.path,
        memtag=note.memtag,
        confidence=note.confidence,
        status=note.status,
        source=note.source,
        created=note.created,
        expires=note.expires,
        supersedes=list(note.supersedes),
        tags=list(note.tags),
        subject=note.subject,
        body=note.body[:char_budget],
        raw_frontmatter=dict(note.raw_frontmatter),
        trust=note.trust,
        last_confirmed=note.last_confirmed,
        contradicted_by=list(note.contradicted_by),
        is_superseded=note.is_superseded,
    )


def pack_vault(
    vault: Path,
    task: str = "",
    budget: int = 8000,
    *,
    candidate_paths: list[Path] | None = None,
    estimator: TokenEstimator | None = None,
) -> PackResult:
    notes = load_vault(vault)
    enrich_vault(notes, vault)
    terms = _task_terms(task)

    allowed: set[Path] | None = None
    if candidate_paths:
        allowed = {path.resolve() for path in candidate_paths}

    skipped_expired = 0
    skipped_deprecated = 0
    skipped_superseded = 0
    skipped_not_candidate = 0
    candidates: list[tuple[float, MemoryMeta]] = []

    for note in notes:
        if allowed is not None and note.path.resolve() not in allowed:
            skipped_not_candidate += 1
            continue
        if note.is_memtagged and note.status == "deprecated":
            skipped_deprecated += 1
            continue
        if note.is_memtagged and note.is_expired:
            skipped_expired += 1
            continue
        if note.is_memtagged and note.is_superseded:
            skipped_superseded += 1
            continue

        relevance = _relevance(note, terms)
        score = (note.trust_score * 0.6) + (relevance * 0.4)
        candidates.append((score, note))

    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[MemoryMeta] = []
    used = 0
    for _, note in candidates:
        remaining = budget - used
        if remaining <= 0:
            break

        rendered = _render_note(note)
        cost = estimate_tokens(rendered, estimator=estimator)

        if cost > remaining:
            if selected:
                continue
            note = _truncate_note(note, remaining)
            rendered = _render_note(note)
            cost = estimate_tokens(rendered, estimator=estimator)
            cost = min(cost, remaining)

        selected.append(note)
        used += cost

    return PackResult(
        selected=selected,
        budget=budget,
        used_tokens=used,
        skipped_expired=skipped_expired,
        skipped_deprecated=skipped_deprecated,
        skipped_superseded=skipped_superseded,
        skipped_not_candidate=skipped_not_candidate,
    )


def format_pack(result: PackResult) -> str:
    chunks: list[str] = []
    for note in result.selected:
        if note.is_memtagged:
            chunks.append(render_frontmatter(note))
        else:
            chunks.append(
                f"<!-- untagged: {note.path.name} -->\n# {note.path.stem}\n\n{note.body}"
            )
    return "\n\n---\n\n".join(chunks).strip() + "\n"
