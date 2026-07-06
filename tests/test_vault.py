from pathlib import Path

from memtag.vault import parse_candidate_paths, resolve_note_path


def test_resolve_note_path_by_filename() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    path = resolve_note_path(vault, "deploy-api-production.md")
    assert path is not None
    assert path.name == "deploy-api-production.md"


def test_parse_candidate_paths_deduplicates() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    lines = [
        "deploy-api-production.md",
        "deploy-api-production.md",
        "# comment",
        "",
        "user-prefs.md",
    ]
    resolved = parse_candidate_paths(vault, lines)
    assert len(resolved) == 2
    assert {p.name for p in resolved} == {"deploy-api-production.md", "user-prefs.md"}


def test_resolve_note_path_absolute(tmp_path: Path) -> None:
    note = tmp_path / "note.md"
    note.write_text("# hi\n", encoding="utf-8")
    assert resolve_note_path(tmp_path, str(note)) == note.resolve()
    assert resolve_note_path(tmp_path, "missing.md") is None