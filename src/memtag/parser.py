from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from memtag.models import MemoryMeta, parse_date

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Token estimator: ~4 characters per token for English markdown (GPT-style heuristic).
# Override via estimate_tokens(..., estimator=...) for tiktoken or model-specific counts.
TokenEstimator = Callable[[str], int]
_DEFAULT_CHARS_PER_TOKEN = 4


def _strip_wikilink(value: str) -> str:
    match = WIKILINK_RE.fullmatch(value.strip())
    if match:
        return match.group(1)
    return value.strip()


def _normalize_supersedes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [_strip_wikilink(value)]
    if isinstance(value, list):
        return [_strip_wikilink(str(v)) for v in value]
    return [_strip_wikilink(str(value))]


def _normalize_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def _normalize_contradicted_by(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


def parse_memory_file(path: Path) -> MemoryMeta:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return MemoryMeta(path=path, body=text.strip())

    raw = yaml.safe_load(match.group(1)) or {}
    if not isinstance(raw, dict):
        raw = {}

    body = text[match.end() :].strip()
    return MemoryMeta(
        path=path,
        memtag=str(raw["memtag"]) if raw.get("memtag") is not None else None,
        confidence=float(raw["confidence"]) if raw.get("confidence") is not None else None,
        status=str(raw["status"]) if raw.get("status") is not None else None,
        source=str(raw["source"]) if raw.get("source") is not None else None,
        created=parse_date(raw.get("created")),
        expires=parse_date(raw.get("expires")),
        supersedes=_normalize_supersedes(raw.get("supersedes")),
        tags=_normalize_tags(raw.get("tags")),
        subject=str(raw["subject"]) if raw.get("subject") is not None else None,
        body=body,
        raw_frontmatter=raw,
        trust=float(raw["trust"]) if raw.get("trust") is not None else None,
        last_confirmed=parse_date(raw.get("last_confirmed")),
        contradicted_by=_normalize_contradicted_by(raw.get("contradicted_by")),
    )


def render_frontmatter(meta: MemoryMeta, *, include_derived: bool = True) -> str:
    data: dict[str, Any] = {}
    if meta.memtag is not None:
        data["memtag"] = meta.memtag
    if meta.confidence is not None:
        data["confidence"] = meta.confidence
    if meta.status is not None:
        data["status"] = meta.status
    if meta.source is not None:
        data["source"] = meta.source
    if meta.created is not None:
        data["created"] = meta.created.isoformat()
    if meta.expires is not None:
        data["expires"] = meta.expires.isoformat()
    if meta.supersedes:
        data["supersedes"] = meta.supersedes if len(meta.supersedes) > 1 else meta.supersedes[0]
    if meta.tags:
        data["tags"] = meta.tags
    if meta.subject is not None:
        data["subject"] = meta.subject

    if include_derived and meta.is_memtagged:
        if meta.trust is not None:
            data["trust"] = round(meta.trust, 4)
        if meta.last_confirmed is not None:
            data["last_confirmed"] = meta.last_confirmed.isoformat()
        if meta.contradicted_by:
            data["contradicted_by"] = meta.contradicted_by

    header = yaml.safe_dump(data, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{header}\n---\n\n{meta.body}".rstrip() + "\n"


def wikilink_to_slug(link: str) -> str:
    target = link.split("|", 1)[0].strip()
    if target.endswith(".md"):
        target = target[:-3]
    return Path(target).name.lower()


def estimate_tokens(text: str, estimator: TokenEstimator | None = None) -> int:
    if estimator is not None:
        return max(1, estimator(text))
    return max(1, len(text) // _DEFAULT_CHARS_PER_TOKEN)
