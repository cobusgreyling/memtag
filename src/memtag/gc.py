from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from memtag.models import MemoryStatus
from memtag.parser import render_frontmatter
from memtag.vault import load_vault


@dataclass
class GcResult:
    archived: list[Path]
    marked_deprecated: list[Path]
    dry_run: bool


def gc_vault(vault: Path, *, dry_run: bool = False) -> GcResult:
    archive_dir = vault / ".memtag" / "archive"
    archived: list[Path] = []
    marked_deprecated: list[Path] = []

    if not dry_run:
        archive_dir.mkdir(parents=True, exist_ok=True)

    for note in load_vault(vault):
        if not note.is_memtagged:
            continue

        should_archive = note.is_expired or note.status == MemoryStatus.DEPRECATED.value
        if not should_archive:
            continue

        rel = note.path.relative_to(vault)
        target = archive_dir / rel
        if dry_run:
            archived.append(note.path)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        if note.is_expired and note.status != MemoryStatus.DEPRECATED.value:
            note.status = MemoryStatus.DEPRECATED.value
            note.path.write_text(render_frontmatter(note), encoding="utf-8")
            marked_deprecated.append(note.path)

        shutil.move(str(note.path), str(target))
        archived.append(note.path)

    return GcResult(archived=archived, marked_deprecated=marked_deprecated, dry_run=dry_run)