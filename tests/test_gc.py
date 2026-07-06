from pathlib import Path

from memtag.gc import gc_vault


def test_gc_dry_run(tmp_path: Path) -> None:
    note = tmp_path / "stale.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.5
status: hypothesis
source: agent:test/loop-1
expires: 2020-01-01
---

stale
""",
        encoding="utf-8",
    )
    result = gc_vault(tmp_path, dry_run=True)
    assert len(result.archived) == 1
    assert note.exists()


def test_gc_archives_expired_note(tmp_path: Path) -> None:
    note = tmp_path / "stale.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.5
status: hypothesis
source: agent:test/loop-1
expires: 2020-01-01
---

stale
""",
        encoding="utf-8",
    )
    result = gc_vault(tmp_path, dry_run=False)
    assert len(result.archived) == 1
    assert not note.exists()
    archived = tmp_path / ".memtag" / "archive" / "stale.md"
    assert archived.exists()
    assert "deprecated" in archived.read_text(encoding="utf-8")


def test_gc_archives_superseded_note(tmp_path: Path) -> None:
    old = tmp_path / "old.md"
    old.write_text(
        """---
memtag: "1"
confidence: 0.7
status: hypothesis
source: agent:test/loop-1
expires: 2027-01-01
---

old
""",
        encoding="utf-8",
    )
    new = tmp_path / "new.md"
    new.write_text(
        """---
memtag: "1"
confidence: 0.9
status: fact
source: human:test
created: 2026-07-04
expires: 2027-07-04
supersedes: "[[old]]"
---

new
""",
        encoding="utf-8",
    )
    result = gc_vault(tmp_path, dry_run=False)
    assert old.resolve() in {p.resolve() for p in result.archived}
    assert not old.exists()
    assert new.exists()
