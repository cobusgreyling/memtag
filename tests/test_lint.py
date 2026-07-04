from pathlib import Path

from memtag.lint import lint_vault


def test_lint_example_vault() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    report = lint_vault(vault)
    assert report.scanned >= 5
    assert report.memtagged >= 4
    codes = {issue.code for issue in report.issues}
    assert "EXPIRED" in codes
    assert "POSSIBLE_CONTRADICTION" in codes