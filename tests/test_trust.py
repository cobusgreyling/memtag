from datetime import date
from pathlib import Path

from memtag.lint import lint_vault
from memtag.parser import parse_memory_file
from memtag.trust import enrich_vault
from memtag.vault import load_vault


def _write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def test_trust_prefers_human_over_agent(tmp_path: Path) -> None:
    _write(
        tmp_path / "human.md",
        """---
memtag: "1"
confidence: 0.6
status: fact
source: human:cobus
created: 2026-07-04
tags: [deploy]
---

Human note.
""",
    )
    _write(
        tmp_path / "agent.md",
        """---
memtag: "1"
confidence: 0.9
status: hypothesis
source: agent:cursor/loop-1
created: 2026-07-04
tags: [deploy]
---

Agent note.
""",
    )
    notes = load_vault(tmp_path)
    enrich_vault(notes, tmp_path)
    human = next(n for n in notes if n.path.stem == "human")
    agent = next(n for n in notes if n.path.stem == "agent")
    assert human.trust > agent.trust


def test_supersedes_zeros_replaced_note(tmp_path: Path) -> None:
    _write(
        tmp_path / "old.md",
        """---
memtag: "1"
confidence: 0.8
status: hypothesis
source: agent:cursor/loop-1
created: 2026-06-01
expires: 2027-06-01
tags: [deploy]
---

Old deploy note.
""",
    )
    _write(
        tmp_path / "new.md",
        """---
memtag: "1"
confidence: 0.85
status: fact
source: human:cobus
created: 2026-07-04
expires: 2027-07-04
supersedes: "[[old]]"
tags: [deploy]
---

New deploy note.
""",
    )
    notes = load_vault(tmp_path)
    enrich_vault(notes, tmp_path)
    old = next(n for n in notes if n.path.stem == "old")
    new = next(n for n in notes if n.path.stem == "new")
    assert old.trust == 0.0
    assert old.is_superseded
    assert new.trust > 0.0
    assert not new.is_superseded


def test_contradiction_downweights_lower_trust(tmp_path: Path) -> None:
    _write(
        tmp_path / "a.md",
        """---
memtag: "1"
confidence: 0.9
status: fact
source: human:cobus
created: 2026-07-04
subject: api-port
---

Port 443.
""",
    )
    _write(
        tmp_path / "b.md",
        """---
memtag: "1"
confidence: 0.6
status: hypothesis
source: agent:cursor/loop-2
created: 2026-07-04
subject: api-port
---

Port 8080.
""",
    )
    notes = load_vault(tmp_path)
    derived = enrich_vault(notes, tmp_path)
    loser = next(n for n in notes if n.path.stem == "b")
    assert loser.trust < 0.6
    assert "a" in derived[loser.path].contradicted_by


def test_lint_write_persists_derived(tmp_path: Path) -> None:
    _write(
        tmp_path / "note.md",
        """---
memtag: "1"
confidence: 0.8
status: fact
source: human:test
created: 2026-07-04
---

Persist me.
""",
    )
    lint_vault(tmp_path, write=True)
    reparsed = parse_memory_file(tmp_path / "note.md")
    assert reparsed.trust is not None
    assert reparsed.last_confirmed == date(2026, 7, 4)
    text = (tmp_path / "note.md").read_text(encoding="utf-8")
    assert "trust:" in text


def test_contradiction_requires_subject_or_supersedes_collision(tmp_path: Path) -> None:
    _write(
        tmp_path / "left.md",
        """---
memtag: "1"
confidence: 0.8
status: fact
source: human:a
created: 2026-07-04
tags: [shared]
---

Left claim.
""",
    )
    _write(
        tmp_path / "right.md",
        """---
memtag: "1"
confidence: 0.7
status: fact
source: human:b
created: 2026-07-04
tags: [shared]
---

Right claim.
""",
    )
    report = lint_vault(tmp_path)
    assert not any(i.code == "POSSIBLE_CONTRADICTION" for i in report.issues)

    report_tags = lint_vault(tmp_path, detect_tag_contradictions=True)
    assert any(i.code == "POSSIBLE_CONTRADICTION" for i in report_tags.issues)
