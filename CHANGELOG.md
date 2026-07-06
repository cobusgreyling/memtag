# Changelog

All notable changes to this project are documented here. Package version follows
[semver](https://semver.org/). Spec version (`memtag: "1"` in frontmatter) is
independent.

## [0.1.0] - 2026-07-06

### Added

- Vault-level derived trust (`trust.py`) with supersession and contradiction decay
- `memtag lint --write` to persist derived frontmatter
- `memtag pack --paths` and `--stdin` for retrieval-tool composition
- Lint rules: `MISSING_EXPIRES`, `DERIVED_TAMPERED`
- `examples/recollect-demo.sh` end-to-end composition demo
- CI workflow with ruff, pytest, and coverage
- PyPI publish workflow on GitHub release
- Apache-2.0 `LICENSE`

### Changed

- `pack` and `gc` are supersession-aware; contradictions use `subject` by default
- README and SPEC aligned with v1 shipped scope