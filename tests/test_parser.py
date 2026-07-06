from datetime import date
from pathlib import Path

from memtag.parser import estimate_tokens, parse_memory_file, render_frontmatter


def test_parse_memtagged_note(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text(
        """---
memtag: "1"
confidence: 0.8
status: fact
source: human:test
created: 2026-07-04
expires: 2026-08-04
tags: [deploy]
trust: 0.91
last_confirmed: 2026-07-04
contradicted_by: []
---

Hello world
""",
        encoding="utf-8",
    )
    note = parse_memory_file(path)
    assert note.is_memtagged
    assert note.confidence == 0.8
    assert note.trust == 0.91
    assert note.last_confirmed == date(2026, 7, 4)
    assert note.created == date(2026, 7, 4)
    assert note.tags == ["deploy"]
    assert note.body == "Hello world"


def test_render_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("---\nmemtag: '1'\nstatus: fact\n---\n\nBody\n", encoding="utf-8")
    note = parse_memory_file(path)
    note.trust = 0.75
    note.last_confirmed = date(2026, 7, 4)
    rendered = render_frontmatter(note)
    roundtrip_path = tmp_path / "roundtrip.md"
    roundtrip_path.write_text(rendered, encoding="utf-8")
    reparsed = parse_memory_file(roundtrip_path)
    assert reparsed.memtag == note.memtag
    assert reparsed.status == note.status
    assert reparsed.body == note.body
    assert reparsed.trust == note.trust
    assert reparsed.last_confirmed == note.last_confirmed


def test_estimate_tokens_custom_estimator() -> None:
    assert estimate_tokens("hello world", estimator=lambda t: len(t)) == 11
    assert estimate_tokens("abcd") == 1
