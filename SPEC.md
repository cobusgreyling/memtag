# memtag specification v1

memtag is a frontmatter convention for markdown files in agent wikis (Obsidian vaults, repo docs, loop journals).

It does not replace your memory store. It makes **human-readable wiki files** safe to feed back into agents by separating what authors declare from what memtag derives.

## Core rule

**Authors touch declared. memtag owns derived. `pack` and `gc` read derived `trust`, never raw `confidence`.**

- `confidence` is a **prior** — the author's starting guess at write time.
- `trust` is the **product** — memtag's computed score after provenance, decay, contradictions, and human touch.

Storing agent self-reported confidence as ground truth is circular. memtag breaks the loop.

## Schema

### Declared (author writes — human or agent)

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| `memtag` | yes | string | Spec version. Current: `"1"` |
| `source` | yes | string | Provenance. See [Source](#source) |
| `confidence` | yes | float | 0.0–1.0 prior at write time — not ground truth |
| `status` | yes | enum | `fact`, `hypothesis`, or `deprecated` |
| `created` | no | ISO date | When the note was written |
| `expires` | no | ISO date | Hard stop — note should not be packed after this date |
| `supersedes` | no | string or list | Wikilink(s) this note explicitly replaces |
| `subject` | no | string | Shared key for contradiction detection (same subject + different body) |
| `tags` | no | string or list | Topic tags for relevance ranking |

The note **body** is the atomic claim. A separate `claim` field may be added in a future spec revision; v1 uses body text.

### Derived (memtag computes — never hand-edited)

| Field | Type | Description |
|-------|------|-------------|
| `trust` | float | 0.0–1.0 score `pack` ranks on |
| `last_confirmed` | ISO date | Last human touch or explicit confirmation |
| `contradicted_by` | list | Note stems that conflict with this one |

`memtag lint --write` recomputes and persists the derived block. `pack` and `gc` load persisted values and recompute vault-level trust on each run.

Authors must never edit derived fields. CI may reject hand-edited `trust` values.

## Source

`source` records provenance and sets the trust floor.

| Prefix | Meaning | Example |
|--------|---------|---------|
| `human:` | Person-authored or blessed | `human:cobus` |
| `agent:` | Agent-written | `agent:cursor/loop-7` |
| `tool:` | Fetched from an external tool | `tool:gh-api/pr-412` |

Human-sourced notes receive a trust boost. Agent and tool notes decay faster unless confirmed.

## Status

| Value | Meaning | Packing |
|-------|---------|---------|
| `fact` | Validated or human-authored | Packed; higher trust floor |
| `hypothesis` | Agent guess, unverified | Packed with penalty; should set `expires` |
| `deprecated` | Superseded or rejected | Never packed; `gc` archives |

Mapping to informal labels: `fact` ≈ active/confirmed, `hypothesis` ≈ draft/guess, `deprecated` ≈ retired.

## Trust signals

memtag updates `trust` from behavior. Declared `confidence` is only the starting point.

| Signal | What it means | Effect on trust |
|--------|---------------|-----------------|
| **Supersedes** | A newer note replaces this one | Trust → 0; excluded from `pack` |
| **Contradiction** | A higher-trust note conflicts with this one | ×0.5 decay; `contradicted_by` set |
| **Human touch** | A person edited or blessed the note | Strong boost; resets confirmation clock |
| **Half-life** | Time since last confirmation vs. type-based decay rate | Gradual decay (v2) |
| **Provenance** | `human:` vs `agent:` vs `tool:` | Sets the floor |
| **Outcome** (v2) | Packing this note preceded a success/failure | Reinforcement |

### v1 trust computation (vault-level)

Trust is computed in a vault-wide pass, not per-note in isolation:

1. Start from declared `confidence` (default 0.5 if missing).
2. Adjust by `status`: `fact` +0.15, `hypothesis` −0.10, `deprecated` → 0.
3. Boost `human:` sources +0.10.
4. Multiply by 0.25 if past `expires`.
5. Zero-out notes reachable through a `supersedes` chain.
6. Down-weight notes contradicted by a higher-trust peer (×0.5).
7. Combine with task relevance in `pack`: `score = trust × 0.6 + relevance × 0.4`.

### Contradiction detection

By default, contradictions require one of:

- **Subject collision** — active notes share a `subject` with different body text.
- **Supersedes collision** — multiple active notes claim to supersede the same target with different body text.

Pass `--tag-contradictions` to `lint` for the legacy O(n²) tag-overlap heuristic.

## Example

```yaml
---
memtag: "1"
source: human:cobus
confidence: 0.85
status: fact
created: 2026-07-04
expires: 2026-10-04
supersedes: "[[old-user-prefs]]"
tags: [preferences, editor]
---

User prefers terse responses and no emojis.
```

After `memtag lint --write`:

```yaml
trust: 0.91
last_confirmed: 2026-07-04
contradicted_by: []
```

## CLI contract

**sense → select → sweep**

| Command | Role | Purpose |
|---------|------|---------|
| `memtag lint <vault>` | sense | Validate declared fields; recompute trust; find stale/contradictory notes |
| `memtag pack <vault> --task "..." --budget 8000` | select | Return budgeted context ranked by derived trust |
| `memtag gc <vault>` | sweep | Move expired/deprecated/superseded notes to `.memtag/archive/` (never delete) |

### Flags

| Flag | Commands | Description |
|------|----------|-------------|
| `--json` | all | Machine-readable output for CI and agents |
| `--strict` | lint | Exit non-zero on warnings |
| `--write` | lint | Persist derived trust block to each note |
| `--tag-contradictions` | lint | Enable tag-overlap contradiction heuristic |
| `--task` | pack | Current task string for relevance ranking |
| `--budget` | pack | Token budget (default: 8000) |
| `--paths` | pack | Only consider these vault notes (repeatable) |
| `--stdin` | pack | Read additional candidate paths from stdin (one per line) |
| `--stats` | pack | Print packing stats to stderr |
| `--dry-run` | gc | Show what would be archived |

### Lint codes

| Code | Severity | Meaning |
|------|----------|---------|
| `MISSING_EXPIRES` | warning | `hypothesis` without `expires` |
| `DERIVED_TAMPERED` | error | Persisted `trust` / `last_confirmed` / `contradicted_by` do not match recomputed values |

## Agent integration

Agents call `memtag pack` at loop start and write new notes with declared frontmatter at loop end.

```bash
# In your agent harness (Grok, Cursor, Claude Code, etc.)
CONTEXT=$(memtag pack ~/vault --task "$GOAL" --budget 8000)
# ... run loop ...
memtag lint ~/vault --write --json --strict
```

Agents write **declared** fields only. They must not set `trust`, `last_confirmed`, or `contradicted_by`.

## Composability

memtag is a **vault hygiene CLI**, not an agent chat CLI.

- **recollect** — semantic retrieval over embeddings; memtag ranks markdown trust. `recollect | memtag pack` is the intended demo.
- **goal-engineering** — run `memtag lint` in CI next to `goal-audit`
- **Any agent shell** — one subprocess; stdout becomes context

## Roadmap

| Version | Scope |
|---------|-------|
| **v1** (`0.1.0`) | Declared schema, vault-level derived trust, persisted derived block, supersession-aware `pack`/`gc` |
| **v2** | Outcome reinforcement from loop success/failure |

## Versioning

When `memtag` frontmatter is present, the `memtag` field must equal `"1"` for this spec. Tools should warn on unknown versions and document migration paths before bumping to `"2"`.

Package version (`0.1.0`) follows semver and is independent of the spec version (`"1"`).