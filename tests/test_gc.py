from datetime import date
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