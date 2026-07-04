from datetime import date
from pathlib import Path

from memtag.parser import parse_memory_file, render_frontmatter


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
---

Hello world
""",
        encoding="utf-8",
    )
    note = parse_memory_file(path)
    assert note.is_memtagged
    assert note.confidence == 0.8
    assert note.created == date(2026, 7, 4)
    assert note.tags == ["deploy"]
    assert note.body == "Hello world"


def test_render_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "note.md"
    path.write_text("---\nmemtag: '1'\nstatus: fact\n---\n\nBody\n", encoding="utf-8")
    note = parse_memory_file(path)
    rendered = render_frontmatter(note)
    reparsed = parse_memory_file(path)
    reparsed.body = note.body
    assert "Body" in rendered