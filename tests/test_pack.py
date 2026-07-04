from pathlib import Path

from memtag.pack import format_pack, pack_vault


def test_pack_respects_budget() -> None:
    vault = Path(__file__).resolve().parents[1] / "examples" / "vault"
    result = pack_vault(vault, task="deploy API", budget=500)
    assert result.selected
    assert result.used_tokens <= 500
    output = format_pack(result)
    assert "deploy" in output.lower() or "api" in output.lower()