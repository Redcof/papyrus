"""CLI for cost-controlled, resumable chapter drafting and publishing."""
import argparse
import json
import sys

from .catalog import ROOT, chapters, get_chapter, relevant_refs, syllabus
from .quality import inspect, ensure_reference_section

OUTPUT = ROOT / "output"


def chapter_path(ch, status):
    return OUTPUT / status / f"chapter_{ch['number']:02d}.md"


def write_report(ch, status, report):
    path = OUTPUT / "reports" / f"chapter_{ch['number']:02d}_{status}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def selected(args):
    all_chapters = list(chapters())
    if args.chapter is not None:
        ch = get_chapter(args.chapter)
        if ch is None:
            raise ValueError(f"Unknown chapter: {args.chapter}")
        return [ch]
    if args.part is not None:
        return [c for c in all_chapters if c["part_number"] == args.part]
    if args.all:
        return all_chapters
    return [all_chapters[0]]


def draft(args):
    candidates = selected(args)
    if args.all and not args.confirm_cost and not args.dry_run:
        raise ValueError("--all requires --confirm-cost; 60 chapters can incur substantial LLM costs")
    if args.limit:
        candidates = candidates[:args.limit]
    if args.dry_run:
        for ch in candidates:
            print(f"{ch['number']:02d} | {ch['part_title']} | {ch['title']}")
        print(f"{len(candidates)} chapter(s) selected; no LLM calls made")
        return
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from .crew import generate
    for ch in candidates:
        target = chapter_path(ch, "drafts")
        if target.exists() and not args.force:
            print(f"SKIP existing: {target.name} (use --force to regenerate)")
            continue
        print(f"Generating chapter {ch['number']:02d}: {ch['title']}", flush=True)
        raw = generate(ch)
        refs = relevant_refs(ch)
        content = ensure_reference_section(raw, refs)
        report = inspect(content, ch, refs)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        write_report(ch, "draft", report)
        print(f"Saved {target}; static checks passed={report['passed_static_checks']}")
        for issue in report["issues"]:
            print("  REVIEW:", issue)


def validate(args):
    ch = get_chapter(args.chapter)
    if ch is None:
        raise ValueError("Unknown chapter")
    path = chapter_path(ch, args.status)
    if not path.exists():
        raise FileNotFoundError(path)
    report = inspect(path.read_text(encoding="utf-8"), ch, relevant_refs(ch))
    print(json.dumps(report, indent=2))
    if not report["passed_static_checks"]:
        sys.exit(1)


def approve(args):
    ch = get_chapter(args.chapter)
    if ch is None:
        raise ValueError("Unknown chapter")
    src = chapter_path(ch, "drafts")
    dst = chapter_path(ch, "approved")
    if not src.exists():
        raise FileNotFoundError(src)
    if dst.exists() and not args.force:
        raise ValueError("Approved file already exists; use --force to replace")
    content = src.read_text(encoding="utf-8")
    report = inspect(content, ch, relevant_refs(ch))
    if not report["passed_static_checks"]:
        raise ValueError("Static checks failed: " + "; ".join(report["issues"]))
    if not args.reviewed:
        raise ValueError("Requires --reviewed: you must actually review mathematics, citations, code and claims")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(content, encoding="utf-8")
    write_report(ch, "approved", report)
    print(f"Approved: {dst}")


def assemble(args):
    syllabus_data = syllabus()
    sections = [f"# {syllabus_data['title']}", f"*{syllabus_data['subtitle']}*", "", f"Edition: {syllabus_data['edition']}", ""]
    count = 0
    missing = []
    for part in syllabus_data["parts"]:
        sections.append(f"\n# Part {part['number']}: {part['title']}\n")
        for ch in part["chapters"]:
            src = chapter_path(ch, "approved")
            if not src.exists() and args.include_drafts:
                src = chapter_path(ch, "drafts")
            if not src.exists():
                missing.append(ch["number"])
                continue
            count += 1
            content = src.read_text(encoding="utf-8")
            if src.parent.name == "drafts":
                sections.append(f"**UNREVIEWED DRAFT — CHAPTER {ch['number']}**\n")
            sections.append(content)
            sections.append("\n\n---\n")
    target = OUTPUT / "books" / "principal_ai_engineers_handbook.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(sections), encoding="utf-8")
    print(f"Assembled {count}/60 chapters into {target}")
    if missing:
        print(f"Missing chapters ({len(missing)}): {', '.join(map(str, missing))}")
    print("To export DOCX/PDF, install Pandoc (and a LaTeX engine for PDF). See README.")


def main():
    parser = argparse.ArgumentParser(description="CrewAI technical book authoring project")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("draft", help="Generate one or more draft chapters")
    p.add_argument("--chapter", type=int)
    p.add_argument("--part", type=int)
    p.add_argument("--all", action="store_true")
    p.add_argument("--limit", type=int)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--confirm-cost", action="store_true")
    p.set_defaults(func=draft)
    p = sub.add_parser("validate")
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--status", choices=["drafts", "approved"], default="drafts")
    p.set_defaults(func=validate)
    p = sub.add_parser("approve")
    p.add_argument("--chapter", type=int, required=True)
    p.add_argument("--reviewed", action="store_true", help="Affirm independent technical review")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=approve)
    p = sub.add_parser("assemble")
    p.add_argument("--include-drafts", action="store_true")
    p.set_defaults(func=assemble)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        parser.error(str(exc))

if __name__ == "__main__":
    main()
