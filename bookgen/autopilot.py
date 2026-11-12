"""Papyrus v0.2 research, authoring, verification and approved-only publishing CLI."""
import argparse
import json
from pathlib import Path

from .catalog import ROOT, chapters, get_chapter
from .pipeline import run_chapter, chapter_artifacts
from .publishing import assemble_approved, export_book
from .research import load_bundle, research_chapter, save_bundle
from .verification import approval_allowed, save_report, verify_chapter

OUTPUT = ROOT / "output"


def chosen(args):
    items = list(chapters())
    if args.chapter is not None:
        chapter = get_chapter(args.chapter)
        if chapter is None:
            raise ValueError("Unknown chapter number")
        return [chapter]
    if args.part is not None:
        selected = [ch for ch in items if ch["part_number"] == args.part]
        if not selected:
            raise ValueError("Unknown part number")
        return selected
    if args.all:
        return items
    return [items[0]]


def cmd_research(args):
    for chapter in chosen(args):
        path = chapter_artifacts(OUTPUT, chapter)["evidence"]
        if path.exists() and not args.force:
            print(f"SKIP cached evidence: {path}")
            continue
        bundle = research_chapter(chapter, max_discovered=args.max_discovered)
        save_bundle(bundle, path)
        print(f"Research chapter {chapter['number']}: {len(bundle['sources'])} sources; "
              f"{len(bundle['errors'])} lookup errors; {path}")


def cmd_pipeline(args):
    targets = chosen(args)
    if args.all and not args.dry_run and not args.research_only and not args.confirm_cost:
        raise ValueError("Generating all chapters requires --confirm-cost")
    for chapter in targets:
        if args.dry_run:
            print(f"{chapter['number']:02d} {chapter['title']}")
            continue
        result = run_chapter(chapter, OUTPUT, research=not args.no_research,
                             write=not args.research_only, refresh=args.force,
                             max_discovered=args.max_discovered)
        print(json.dumps(result, indent=2))


def cmd_verify(args):
    chapter = get_chapter(args.chapter)
    if chapter is None:
        raise ValueError("Unknown chapter")
    paths = chapter_artifacts(OUTPUT, chapter)
    if not paths["draft"].exists() or not paths["evidence"].exists():
        raise FileNotFoundError("Both draft and research bundle must exist")
    report = verify_chapter(paths["draft"].read_text(encoding="utf-8"), chapter,
                            load_bundle(paths["evidence"]), run_mermaid=args.render_mermaid)
    save_report(report, paths["report"])
    print(json.dumps(report, indent=2))
    if not report["passed_gate"]:
        raise ValueError("Verification gate failed")


def cmd_approve(args):
    chapter = get_chapter(args.chapter)
    if chapter is None:
        raise ValueError("Unknown chapter")
    paths = chapter_artifacts(OUTPUT, chapter)
    if not args.reviewed:
        raise ValueError("Human review required: --reviewed must assert review of source support, "
                         "math, code and factual claims")
    if not paths["draft"].is_file() or not paths["evidence"].is_file():
        raise FileNotFoundError("Draft and evidence bundle required")
    text = paths["draft"].read_text(encoding="utf-8")
    report = verify_chapter(text, chapter, load_bundle(paths["evidence"]),
                            run_mermaid=args.render_mermaid)
    save_report(report, paths["report"])
    if not approval_allowed(text, report):
        raise ValueError("Static verification failed: " + "; ".join(report["issues"]))
    target = OUTPUT / "approved" / f"chapter_{chapter['number']:02d}.md"
    if target.exists() and not args.force:
        raise ValueError("Approved chapter exists; use --force after human review")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"Human-approved {target}. This does not imply automatic claim-level proof.")


def cmd_publish(args):
    manuscript, manifest = assemble_approved(OUTPUT, require_complete=args.require_complete)
    print(f"Manuscript: {manuscript} ({len(manifest['chapters'])} chapters, {manifest['status']})")
    if args.format != "md":
        print("Export:", export_book(manuscript, args.format))


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description="Papyrus autonomous research and book publishing")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("research", help="Crossref/OpenAlex metadata search, saved evidence")
    p.add_argument("--chapter", type=int)
    p.add_argument("--part", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-discovered", type=int, default=5)
    p.set_defaults(func=cmd_research)

    p = sub.add_parser("pipeline", help="Research -> CrewAI writing -> static verification")
    p.add_argument("--chapter", type=int)
    p.add_argument("--part", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--research-only", action="store_true")
    p.add_argument("--no-research", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--confirm-cost", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-discovered", type=int, default=5)
    p.set_defaults(func=cmd_pipeline)

    p = sub.add_parser("verify", help="Check citations, headings, Python syntax and diagrams")
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--render-mermaid", action="store_true")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("approve", help="Require explicit human-reviewed draft")
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--reviewed", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--render-mermaid", action="store_true")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("publish", help="Assemble approved-only manuscript and export")
    p.add_argument("--format", choices=["md", "docx", "pdf", "epub"], default="md")
    p.add_argument("--require-complete", action="store_true")
    p.set_defaults(func=cmd_publish)

    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
