from pathlib import Path

from memtag.pack import format_pack, pack_vault


def test_pack_respects_budget() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    result = pack_vault(vault, task="deploy API", budget=500)
    assert result.selected
    assert result.used_tokens <= 500
    output = format_pack(result)
    assert "deploy" in output.lower() or "api" in output.lower()


def test_pack_skips_superseded_staging() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    result = pack_vault(vault, task="deploy API", budget=8000)
    selected = {n.path.name for n in result.selected}
    assert "deploy-api-production.md" in selected
    assert "deploy-api-staging.md" not in selected
    assert result.skipped_superseded >= 1


def test_pack_budget_hard_cap(tmp_path: Path) -> None:
    for i in range(5):
        path = tmp_path / f"note-{i}.md"
        path.write_text(
            f"""---
memtag: "1"
confidence: 0.9
status: fact
source: human:test
created: 2026-07-04
---

{"x" * 200}
""",
            encoding="utf-8",
        )
    result = pack_vault(tmp_path, budget=50)
    assert result.used_tokens <= 50
    assert len(result.selected) >= 1


def test_pack_truncates_single_oversized_note(tmp_path: Path) -> None:
    path = tmp_path / "big.md"
    path.write_text(
        f"""---
memtag: "1"
confidence: 0.9
status: fact
source: human:test
created: 2026-07-04
---

{"word " * 500}
""",
        encoding="utf-8",
    )
    result = pack_vault(tmp_path, budget=40)
    assert result.used_tokens <= 40
    assert len(result.selected) == 1
    assert len(result.selected[0].body) < 500 * 5


def test_pack_candidate_paths_filters_notes(tmp_path: Path) -> None:
    high = tmp_path / "high.md"
    high.write_text(
        """---
memtag: "1"
confidence: 0.9
status: fact
source: human:test
created: 2026-07-04
tags: [deploy]
---

High trust deploy note.
""",
        encoding="utf-8",
    )
    low = tmp_path / "low.md"
    low.write_text(
        """---
memtag: "1"
confidence: 0.2
status: hypothesis
source: agent:test/loop-1
created: 2026-07-04
expires: 2027-01-01
tags: [misc]
---

Low trust misc note.
""",
        encoding="utf-8",
    )

    result = pack_vault(
        tmp_path,
        task="deploy",
        budget=8000,
        candidate_paths=[high.resolve()],
    )
    selected = {n.path.name for n in result.selected}
    assert selected == {"high.md"}
    assert result.skipped_not_candidate == 1


def test_pack_recollect_demo_candidates() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    candidates = [
        (vault / "deploy-api-production.md").resolve(),
        (vault / "deploy-api-staging.md").resolve(),
        (vault / "user-prefs.md").resolve(),
    ]
    result = pack_vault(
        vault,
        task="deploy API",
        budget=8000,
        candidate_paths=candidates,
    )
    selected = {n.path.name for n in result.selected}
    assert "deploy-api-production.md" in selected
    assert "deploy-api-staging.md" not in selected
    assert result.skipped_not_candidate >= 1
