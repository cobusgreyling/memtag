from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from memtag.models import MemoryMeta, MemoryStatus
from memtag.vault import resolve_supersedes_target


@dataclass
class DerivedTrust:
    trust: float
    last_confirmed: date | None = None
    contradicted_by: list[str] = field(default_factory=list)
    is_superseded: bool = False


def _base_trust(note: MemoryMeta) -> float:
    """Compute trust from declared signals only (never from persisted trust)."""
    if not note.is_memtagged:
        return 0.35
    base = note.confidence if note.confidence is not None else 0.5
    if note.status == MemoryStatus.FACT.value:
        base += 0.15
    elif note.status == MemoryStatus.HYPOTHESIS.value:
        base -= 0.1
    elif note.status == MemoryStatus.DEPRECATED.value:
        return 0.0
    if note.is_expired:
        base *= 0.25
    if note.source and note.source.startswith("human:"):
        base += 0.1
    return max(0.0, min(1.0, base))


def _last_confirmed(note: MemoryMeta) -> date | None:
    if note.source and note.source.startswith("human:"):
        return note.created
    return None


def _note_key(note: MemoryMeta) -> str:
    return note.path.stem.lower()


def compute_vault_trust(
    notes: list[MemoryMeta],
    vault: Path,
    *,
    detect_tag_contradictions: bool = False,
) -> dict[Path, DerivedTrust]:
    """Vault-level trust derivation from declared signals and note relationships."""
    supersedes_targets: dict[Path, list[Path]] = {}
    for note in notes:
        if not note.is_memtagged:
            continue
        for link in note.supersedes:
            target_path = resolve_supersedes_target(vault, link)
            if target_path is not None:
                supersedes_targets.setdefault(note.path, []).append(target_path)

    is_superseded: dict[Path, bool] = {note.path: False for note in notes}

    def _mark_replaced(path: Path) -> None:
        if is_superseded[path]:
            return
        is_superseded[path] = True
        for target in supersedes_targets.get(path, []):
            _mark_replaced(target)

    for note in notes:
        if not note.is_memtagged or not note.is_active:
            continue
        for target in supersedes_targets.get(note.path, []):
            _mark_replaced(target)

    derived: dict[Path, DerivedTrust] = {}
    for note in notes:
        trust = 0.0 if is_superseded.get(note.path, False) else _base_trust(note)
        derived[note.path] = DerivedTrust(
            trust=trust,
            last_confirmed=_last_confirmed(note),
            is_superseded=is_superseded.get(note.path, False),
        )

    contradictions = _find_contradictions(
        notes,
        vault,
        detect_tag_contradictions=detect_tag_contradictions,
    )
    for left, right in contradictions:
        left_trust = derived[left.path].trust
        right_trust = derived[right.path].trust
        if left_trust == right_trust:
            continue
        if left_trust > right_trust:
            loser, winner = right, left
        else:
            loser, winner = left, right
        state = derived[loser.path]
        state.trust = max(0.0, state.trust * 0.5)
        winner_key = _note_key(winner)
        if winner_key not in state.contradicted_by:
            state.contradicted_by.append(winner_key)

    return derived


def _find_contradictions(
    notes: list[MemoryMeta],
    vault: Path,
    *,
    detect_tag_contradictions: bool,
) -> list[tuple[MemoryMeta, MemoryMeta]]:
    active = [n for n in notes if n.is_memtagged and n.is_active]
    pairs: list[tuple[MemoryMeta, MemoryMeta]] = []
    seen: set[tuple[str, str]] = set()

    def _add_pair(left: MemoryMeta, right: MemoryMeta) -> None:
        if left.body.strip().lower() == right.body.strip().lower():
            return
        key = tuple(sorted([_note_key(left), _note_key(right)]))
        if key in seen:
            return
        seen.add(key)
        pairs.append((left, right))

    by_supersedes_target: dict[str, list[MemoryMeta]] = {}
    for note in active:
        for link in note.supersedes:
            target = resolve_supersedes_target(vault, link)
            if target is None:
                continue
            by_supersedes_target.setdefault(target.stem.lower(), []).append(note)

    for group in by_supersedes_target.values():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                _add_pair(left, right)

    by_subject: dict[str, list[MemoryMeta]] = {}
    for note in active:
        if note.subject:
            by_subject.setdefault(note.subject.lower(), []).append(note)

    for group in by_subject.values():
        if len(group) < 2:
            continue
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                _add_pair(left, right)

    if detect_tag_contradictions:
        tagged = [n for n in active if n.tags]
        for i, left in enumerate(tagged):
            for right in tagged[i + 1 :]:
                shared = set(left.tags) & set(right.tags)
                if shared:
                    _add_pair(left, right)

    return pairs


def apply_derived_trust(notes: list[MemoryMeta], derived: dict[Path, DerivedTrust]) -> None:
    for note in notes:
        state = derived.get(note.path)
        if state is None:
            continue
        note.trust = state.trust
        note.last_confirmed = state.last_confirmed
        note.contradicted_by = list(state.contradicted_by)
        note.is_superseded = state.is_superseded


def enrich_vault(
    notes: list[MemoryMeta],
    vault: Path,
    *,
    detect_tag_contradictions: bool = False,
) -> dict[Path, DerivedTrust]:
    derived = compute_vault_trust(
        notes,
        vault,
        detect_tag_contradictions=detect_tag_contradictions,
    )
    apply_derived_trust(notes, derived)
    return derived
