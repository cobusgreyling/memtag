from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from memtag import __version__
from memtag.gc import gc_vault
from memtag.lint import lint_vault
from memtag.pack import format_pack, pack_vault
from memtag.vault import parse_candidate_paths


def _read_stdin_candidates() -> list[str]:
    if sys.stdin.isatty():
        return []
    return sys.stdin.read().splitlines()


def cmd_lint(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        print(f"memtag: vault not found: {vault}", file=sys.stderr)
        return 1

    report = lint_vault(
        vault,
        write=args.write,
        detect_tag_contradictions=args.tag_contradictions,
    )
    if args.json:
        payload = {
            "vault": str(vault),
            "scanned": report.scanned,
            "memtagged": report.memtagged,
            "written": report.written,
            "errors": report.error_count,
            "warnings": report.warning_count,
            "issues": [
                {
                    "severity": issue.severity,
                    "code": issue.code,
                    "message": issue.message,
                    "path": str(issue.path),
                    "related": str(issue.related) if issue.related else None,
                }
                for issue in report.issues
            ],
        }
        print(json.dumps(payload, indent=2))
    else:
        print(f"memtag lint — {vault}")
        print(f"scanned {report.scanned} notes ({report.memtagged} memtagged)")
        if report.written:
            print(f"wrote derived block to {report.written} notes")
        if not report.issues:
            print("ok — no issues")
        else:
            for issue in report.issues:
                rel = issue.path.relative_to(vault)
                prefix = issue.severity.upper()
                line = f"[{prefix}] {issue.code} {rel}: {issue.message}"
                if issue.related:
                    line += f" (related: {issue.related.relative_to(vault)})"
                print(line)

    if report.error_count:
        return 2
    if report.warning_count and args.strict:
        return 2
    return 0


def cmd_pack(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        print(f"memtag: vault not found: {vault}", file=sys.stderr)
        return 1

    candidate_lines = list(args.paths or [])
    if args.stdin:
        candidate_lines.extend(_read_stdin_candidates())

    candidate_paths = None
    if candidate_lines:
        candidate_paths = parse_candidate_paths(vault, candidate_lines)
        if not candidate_paths:
            print("memtag: no candidate paths resolved from --paths or stdin", file=sys.stderr)
            return 1

    result = pack_vault(
        vault,
        task=args.task or "",
        budget=args.budget,
        candidate_paths=candidate_paths,
    )
    if args.json:
        payload = {
            "vault": str(vault),
            "task": args.task,
            "budget": result.budget,
            "used_tokens": result.used_tokens,
            "skipped_expired": result.skipped_expired,
            "skipped_deprecated": result.skipped_deprecated,
            "skipped_superseded": result.skipped_superseded,
            "skipped_not_candidate": result.skipped_not_candidate,
            "selected": [str(n.path.relative_to(vault)) for n in result.selected],
            "context": format_pack(result),
        }
        print(json.dumps(payload, indent=2))
    else:
        if args.stats:
            print(
                f"# memtag pack — {len(result.selected)} notes, "
                f"~{result.used_tokens}/{result.budget} tokens",
                file=sys.stderr,
            )
            skipped = (
                f"{result.skipped_expired} expired, "
                f"{result.skipped_deprecated} deprecated, "
                f"{result.skipped_superseded} superseded"
            )
            if result.skipped_not_candidate:
                skipped += f", {result.skipped_not_candidate} not in candidates"
            print(f"# skipped: {skipped}", file=sys.stderr)
        print(format_pack(result), end="")
    return 0


def cmd_gc(args: argparse.Namespace) -> int:
    vault = Path(args.vault).resolve()
    if not vault.is_dir():
        print(f"memtag: vault not found: {vault}", file=sys.stderr)
        return 1

    result = gc_vault(vault, dry_run=args.dry_run)
    if args.json:
        payload = {
            "vault": str(vault),
            "dry_run": result.dry_run,
            "archived": [str(p.relative_to(vault)) for p in result.archived],
            "marked_deprecated": [str(p.relative_to(vault)) for p in result.marked_deprecated],
        }
        print(json.dumps(payload, indent=2))
    else:
        mode = "dry-run" if result.dry_run else "gc"
        print(f"memtag {mode} — {vault}")
        if not result.archived:
            print("ok — nothing to archive")
        else:
            for path in result.archived:
                print(f"archive {path.relative_to(vault)}")
        for path in result.marked_deprecated:
            print(f"deprecated {path.relative_to(vault)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memtag",
        description="Markdown memory hygiene for agent wikis (Obsidian-compatible)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    lint = sub.add_parser("lint", help="Find expired, orphaned, and contradictory memories")
    lint.add_argument("vault", nargs="?", default=".", help="Path to Obsidian vault")
    lint.add_argument("--json", action="store_true", help="JSON output for CI / agents")
    lint.add_argument("--strict", action="store_true", help="Exit non-zero on warnings")
    lint.add_argument(
        "--write",
        action="store_true",
        help="Persist derived trust block to each memtagged note",
    )
    lint.add_argument(
        "--tag-contradictions",
        action="store_true",
        help="Also flag contradictions from shared tags (noisy on large vaults)",
    )
    lint.set_defaults(func=cmd_lint)

    pack = sub.add_parser("pack", help="Pack trustworthy context for the next agent loop")
    pack.add_argument("vault", nargs="?", default=".", help="Path to Obsidian vault")
    pack.add_argument("--task", default="", help="Current task (improves relevance ranking)")
    pack.add_argument("--budget", type=int, default=8000, help="Token budget (default: 8000)")
    pack.add_argument(
        "--paths",
        nargs="+",
        default=[],
        metavar="PATH",
        help="Only consider these vault notes (repeatable)",
    )
    pack.add_argument(
        "--stdin",
        action="store_true",
        help="Read additional candidate paths from stdin (one per line)",
    )
    pack.add_argument("--json", action="store_true", help="JSON output with selected files")
    pack.add_argument("--stats", action="store_true", help="Print packing stats to stderr")
    pack.set_defaults(func=cmd_pack)

    gc = sub.add_parser("gc", help="Archive expired and deprecated memories")
    gc.add_argument("vault", nargs="?", default=".", help="Path to Obsidian vault")
    gc.add_argument("--dry-run", action="store_true", help="Show what would be archived")
    gc.add_argument("--json", action="store_true", help="JSON output")
    gc.set_defaults(func=cmd_gc)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
