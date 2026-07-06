import argparse
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from memtag.cli import cmd_gc, cmd_lint, cmd_pack

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "examples" / "vault"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "memtag.cli", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_version() -> None:
    result = _run("--version")
    assert result.returncode == 0
    assert "memtag 0.1.0" in result.stdout


def test_cli_lint_json_exit_codes() -> None:
    result = _run("lint", str(VAULT), "--json")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["scanned"] >= 5
    assert "issues" in payload


def test_cli_lint_strict_exit_code(tmp_path: Path) -> None:
    note = tmp_path / "guess.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.6
status: hypothesis
source: agent:test/loop-1
created: 2026-07-04
---

No expiry.
""",
        encoding="utf-8",
    )
    result = _run("lint", str(tmp_path), "--strict")
    assert result.returncode == 2


def test_cli_pack_stdin_candidates() -> None:
    stdin = "deploy-api-production.md\ndeploy-api-staging.md\nuser-prefs.md\n"
    result = subprocess.run(
        [sys.executable, "-m", "memtag.cli", "pack", str(VAULT), "--stdin", "--json"],
        cwd=ROOT,
        input=stdin,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "deploy-api-production.md" in payload["selected"]
    assert "deploy-api-staging.md" not in payload["selected"]


def test_cli_pack_missing_vault() -> None:
    result = _run("pack", "/nonexistent/vault")
    assert result.returncode == 1
    assert "vault not found" in result.stderr


def test_cmd_lint_human_output(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        json=False,
        strict=False,
        write=False,
        tag_contradictions=False,
    )
    assert cmd_lint(args) == 0
    output = capsys.readouterr().out
    assert "memtag lint" in output
    assert "scanned" in output


def test_cmd_pack_stats_stderr(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        task="deploy API",
        budget=8000,
        paths=[],
        stdin=False,
        json=False,
        stats=True,
    )
    assert cmd_pack(args) == 0
    err = capsys.readouterr().err
    assert "memtag pack" in err


def test_cmd_pack_paths(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        task="deploy API",
        budget=8000,
        paths=["deploy-api-production.md"],
        stdin=False,
        json=True,
        stats=False,
    )
    assert cmd_pack(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["selected"] == ["deploy-api-production.md"]


def test_cmd_pack_stdin_via_mock(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        task="deploy API",
        budget=8000,
        paths=[],
        stdin=True,
        json=True,
        stats=False,
    )
    with patch("memtag.cli._read_stdin_candidates", return_value=["deploy-api-production.md"]):
        assert cmd_pack(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert "deploy-api-production.md" in payload["selected"]


def test_cmd_gc_dry_run(capsys) -> None:
    args = argparse.Namespace(vault=str(VAULT), dry_run=True, json=False)
    assert cmd_gc(args) == 0
    assert "memtag dry-run" in capsys.readouterr().out


def test_cmd_lint_json(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        json=True,
        strict=False,
        write=False,
        tag_contradictions=False,
    )
    assert cmd_lint(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["vault"].endswith("examples/vault")


def test_cmd_lint_missing_vault(capsys) -> None:
    args = argparse.Namespace(
        vault="/nonexistent/vault",
        json=False,
        strict=False,
        write=False,
        tag_contradictions=False,
    )
    assert cmd_lint(args) == 1


def test_cmd_gc_json(capsys) -> None:
    args = argparse.Namespace(vault=str(VAULT), dry_run=True, json=True)
    assert cmd_gc(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["dry_run"] is True


def test_cmd_lint_strict_exit_code(tmp_path: Path, capsys) -> None:
    note = tmp_path / "guess.md"
    note.write_text(
        """---
memtag: "1"
confidence: 0.6
status: hypothesis
source: agent:test/loop-1
created: 2026-07-04
---

No expiry.
""",
        encoding="utf-8",
    )
    args = argparse.Namespace(
        vault=str(tmp_path),
        json=False,
        strict=True,
        write=False,
        tag_contradictions=False,
    )
    assert cmd_lint(args) == 2


def test_cmd_pack_unresolved_candidates_stderr(capsys) -> None:
    args = argparse.Namespace(
        vault=str(VAULT),
        task="",
        budget=8000,
        paths=[],
        stdin=True,
        json=False,
        stats=False,
    )
    with patch("memtag.cli._read_stdin_candidates", return_value=["missing-note.md"]):
        assert cmd_pack(args) == 1
    assert "no candidate paths resolved" in capsys.readouterr().err