from pathlib import Path

from memtag.lint import lint_vault


def test_lint_example_vault() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    report = lint_vault(vault)
    assert report.scanned >= 5
    assert report.memtagged >= 4
    codes = {issue.code for issue in report.issues}
    assert "EXPIRED" in codes
    assert "SUPERSEDED" in codes
    assert "POSSIBLE_CONTRADICTION" not in codes


def test_lint_missing_expires_on_hypothesis(tmp_path: Path) -> None:
    note = tmp_path / "guess.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.6
status: hypothesis
source: agent:test/loop-1
created: 2026-07-04
---

Guess without expiry.
""",
        encoding="utf-8",
    )
    report = lint_vault(tmp_path)
    assert any(issue.code == "MISSING_EXPIRES" for issue in report.issues)


def test_lint_derived_tampered_trust(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.8
status: fact
source: human:test
created: 2026-07-04
trust: 0.99
last_confirmed: 2026-07-04
contradicted_by: []
---

Tampered trust.
""",
        encoding="utf-8",
    )
    report = lint_vault(tmp_path)
    assert any(issue.code == "DERIVED_TAMPERED" for issue in report.issues)
    assert report.error_count >= 1