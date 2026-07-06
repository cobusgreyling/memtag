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


def resolve_note_path(vault: Path, ref: str) -> Path | None:
    """Resolve a vault-relative path, filename, or absolute path to a markdown note."""
    ref = ref.strip()
    if not ref or ref.startswith("#"):
        return None

    candidate = Path(ref)
    if candidate.is_absolute():
        resolved = candidate.resolve()
        return resolved if resolved.is_file() else None

    direct = (vault / ref).resolve()
    if direct.is_file():
        return direct

    target_name = Path(ref).name.lower()
    if not target_name.endswith(".md"):
        target_name = f"{target_name}.md"

    for path in discover_markdown(vault):
        if path.name.lower() == target_name:
            return path.resolve()
        if path.stem.lower() == Path(ref).stem.lower():
            return path.resolve()
    return None


def parse_candidate_paths(vault: Path, lines: list[str]) -> list[Path]:
    """Resolve candidate note paths from stdin lines or CLI --paths values."""
    resolved: list[Path] = []
    seen: set[Path] = set()
    for line in lines:
        path = resolve_note_path(vault, line)
        if path is None or path in seen:
            continue
        seen.add(path)
        resolved.append(path)
    return resolved


def resolve_supersedes_target(vault: Path, link: str) -> Path | None:
    slug = link.split("|", 1)[0].strip()
    slug_path = slug if slug.endswith(".md") else f"{slug}.md"

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
