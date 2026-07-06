# memtag

[![CI](https://github.com/cobusgreyling/memtag/actions/workflows/ci.yml/badge.svg)](https://github.com/cobusgreyling/memtag/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/memtag)](https://pypi.org/project/memtag/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

**Keeps agent-written wikis trustworthy by tracking how memories decay, not just where they're stored.**

The next bottleneck in agent memory isn't storage or retrieval. It's **decay**. Notes rot: guesses expire, loops contradict each other, agent speculation gets laundered into fact. Retrieval tools make rot easier to find. memtag makes it visible and disposable.

memtag is a hygiene CLI + markdown convention for agent wikis: sense rot, select trusted context, sweep the vault.

## Not an agent. Not a store.

memtag does **not** replace Grok, Cursor, Claude Code, or recollect.

It is a composable hygiene layer — pipe it between your vault and whatever CLI you run:

```bash
memtag pack ./vault --task "deploy API" --budget 8000   # select — the product
memtag lint ./vault --strict                            # sense — the sensor
memtag gc ./vault                                       # sweep — the janitor
```

Pipe `pack` output into your agent harness. Store long-term semantic memory in **recollect**. Govern markdown wikis with **memtag**.

```bash
recollect search "deploy API" | memtag pack ./vault --stdin --task "deploy API" --budget 8000
```

## Why memtag

**Declared trust is a prior. Derived trust is the product.**

Everyone else asks the agent "how confident are you?" and stores the number. That's circular — you're trusting an agent's self-report to decide which agent-writing to trust.

memtag treats declared `confidence` as a starting guess, then computes `trust` from behavior: provenance, expiry, supersedes chains, contradictions, human touch. **Trust isn't a field the agent writes. It's a score memtag computes.** `pack` and `gc` rank on derived `trust`, never raw `confidence`.

See [SPEC.md](SPEC.md) for the full schema and trust signals.

## Install

```bash
pip install memtag
# or from source
pip install -e .
```

## Quick start

```bash
memtag lint examples/vault
memtag pack examples/vault --task "deploy API" --stats
memtag gc examples/vault --dry-run
```

### End-to-end: lint → pack → gc

```bash
# Sense: recompute trust and surface rot
memtag lint examples/vault --write --strict

# Select: pack trusted context for the current task (superseded notes excluded)
memtag pack examples/vault --task "deploy API" --budget 8000 --stats 2>/dev/null | head -40

# Sweep: archive expired, deprecated, and superseded notes
memtag gc examples/vault --dry-run
```

With recollect (or any retrieval tool) in front:

```bash
# Retrieval emits candidate paths (one per line); memtag ranks trust and enforces budget
./examples/recollect-demo.sh | memtag pack examples/vault --stdin --task "deploy API" --budget 4000 --stats

# Or pass candidates explicitly
memtag pack examples/vault --paths deploy-api-production.md user-prefs.md --task "deploy API" --stats
```

`pack` on `examples/vault` selects `deploy-api-production.md` (human fact, supersedes staging) and skips the superseded staging note even when retrieval includes it.

## The convention

Authors write the **declared** block. memtag owns the **derived** block.

```yaml
---
# DECLARED — human or agent writes
memtag: "1"
source: agent:cursor/loop-7
confidence: 0.6                       # prior, not truth
status: hypothesis
created: 2026-07-04
expires: 2026-09-01
supersedes: "[[old-deploy-note]]"
subject: deploy-api                   # optional — groups claims for contradiction detection
tags: [deploy, api]
---

Postgres is on port 5433.

# DERIVED — memtag computes (written back by lint --write)
# trust: 0.42
# last_confirmed: 2026-07-01
# contradicted_by: [note-id]
```

Untagged notes are still packed at low trust. Tagged notes without `expires` on hypotheses get lint warnings.

## Commands

**sense → select → sweep** — `pack` is the headline; the other two keep it honest.

| Command | Role | What it does |
|---------|------|--------------|
| `pack` | select | Assemble a token-budgeted context slice, ranked by derived trust |
| `lint` | sense | Recompute trust; surface contradictions, orphans, and stale confidence |
| `gc` | sweep | Archive expired, deprecated, or superseded notes to `.memtag/archive/` |

All commands support `--json` for CI and agent scripting.

`lint --write` persists the derived block. `lint --tag-contradictions` enables the legacy tag-overlap heuristic (off by default — too noisy on real vaults). `lint` flags hand-edited derived fields (`DERIVED_TAMPERED`) and hypotheses missing `expires` (`MISSING_EXPIRES`).

`pack --stdin` and `pack --paths` narrow packing to retrieval candidates before trust ranking.

## Where it fits

```
┌─────────────┐     shell      ┌─────────────┐
│ Grok/Cursor │ ─────────────► │    memtag   │  ← vault hygiene (markdown)
│ Claude Code │                │ lint/pack/gc│
└─────────────┘                └─────────────┘
       │                              │
       │                              ▼
       │                       Obsidian vault
       │
       └──────────────────────► recollect      ← semantic memory (vectors)
```

- **Composes** — recollect retrieves; memtag ranks trust. `recollect | memtag pack` is the demo.
- **Plain markdown** — Obsidian-compatible frontmatter. No lock-in; reversible in one `sed`.

## Roadmap

| Version | Ships |
|---------|-------|
| **v1** (now, package `0.1.0`) | Vault-level derived trust, supersession-aware `pack`, subject/supersedes contradiction lint, `lint --write`, archive `gc` |
| **v2** | Outcome reinforcement — notes that preceded success/failure adjust trust |

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (bad path, etc.) |
| 2 | lint found errors (or warnings with `--strict`) |

## License

Apache-2.0
