from __future__ import annotations

from pathlib import Path

from memtag.models import MemoryMeta
from memtag.parser import parse_memory_file

SKIP_DIRS = {".git", ".memtag", ".obsidian", "node_modules", "__pycache__"}


def discover_markdown(vault: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(vault.rglob("*.md")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        files.append(path)
    return files


def load_vault(vault: Path) -> list[MemoryMeta]:
    return [parse_memory_file(path) for path in discover_markdown(vault)]


def resolve_supersedes_target(vault: Path, link: str) -> Path | None:
    slug = link.split("|", 1)[0].strip()
    if slug.endswith(".md"):
        slug_path = slug
    else:
        slug_path = f"{slug}.md"

    direct = vault / slug_path
    if direct.exists():
        return direct

    target_name = Path(slug_path).name.lower()
    for candidate in discover_markdown(vault):
        if candidate.name.lower() == target_name:
            return candidate
        if candidate.stem.lower() == Path(slug).stem.lower():
            return candidate
    return None