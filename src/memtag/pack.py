from __future__ import annotations

import re
from pathlib import Path

from memtag.models import MemoryMeta, PackResult
from memtag.parser import estimate_tokens, render_frontmatter
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
        ]
    ).lower()
    note_terms = set(TOKEN_RE.findall(haystack))
    if not note_terms:
        return 0.0
    overlap = len(terms & note_terms)
    return overlap / max(len(terms), 1)


def pack_vault(vault: Path, task: str = "", budget: int = 8000) -> PackResult:
    notes = load_vault(vault)
    terms = _task_terms(task)

    skipped_expired = 0
    skipped_deprecated = 0
    candidates: list[tuple[float, MemoryMeta]] = []

    for note in notes:
        if note.is_memtagged and note.status == "deprecated":
            skipped_deprecated += 1
            continue
        if note.is_memtagged and note.is_expired:
            skipped_expired += 1
            continue

        relevance = _relevance(note, terms)
        score = (note.trust_score * 0.6) + (relevance * 0.4)
        candidates.append((score, note))

    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[MemoryMeta] = []
    used = 0
    for _, note in candidates:
        rendered = render_frontmatter(note) if note.is_memtagged else f"# {note.path.stem}\n\n{note.body}\n"
        cost = estimate_tokens(rendered)
        if used + cost > budget and selected:
            continue
        if used + cost > budget:
            # Always include at least one note, truncated if needed.
            note = MemoryMeta(
                path=note.path,
                memtag=note.memtag,
                confidence=note.confidence,
                status=note.status,
                source=note.source,
                created=note.created,
                expires=note.expires,
                supersedes=list(note.supersedes),
                tags=list(note.tags),
                body=note.body[: budget * 4],
                raw_frontmatter=dict(note.raw_frontmatter),
            )
            rendered = render_frontmatter(note) if note.is_memtagged else note.body
            cost = estimate_tokens(rendered)
        selected.append(note)
        used += cost
        if used >= budget:
            break

    return PackResult(
        selected=selected,
        budget=budget,
        used_tokens=used,
        skipped_expired=skipped_expired,
        skipped_deprecated=skipped_deprecated,
    )


def format_pack(result: PackResult) -> str:
    chunks: list[str] = []
    for note in result.selected:
        if note.is_memtagged:
            chunks.append(render_frontmatter(note))
        else:
            chunks.append(f"<!-- untagged: {note.path.name} -->\n# {note.path.stem}\n\n{note.body}")
    return "\n\n---\n\n".join(chunks).strip() + "\n"