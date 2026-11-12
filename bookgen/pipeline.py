"""Resumable research -> authoring -> verification orchestration."""
from pathlib import Path

from .catalog import relevant_refs
from .quality import ensure_reference_section
from .research import research_chapter, save_bundle, load_bundle
from .verification import verify_chapter, save_report


def chapter_artifacts(output, chapter):
    key = f"chapter_{chapter['number']:02d}"
    root = Path(output)
    return {"evidence": root / "research" / f"{key}.json",
            "draft": root / "drafts" / f"{key}.md",
            "report": root / "reports" / f"{key}_verification.json"}


def run_chapter(chapter, output, *, research=True, write=True, refresh=False,
                max_discovered=5, research_func=research_chapter, author=None):
    paths = chapter_artifacts(output, chapter)
    if research and (refresh or not paths["evidence"].exists()):
        evidence = research_func(chapter, max_discovered=max_discovered)
        save_bundle(evidence, paths["evidence"])
    elif paths["evidence"].exists():
        evidence = load_bundle(paths["evidence"])
    else:
        evidence = {"chapter": chapter["number"], "topic": chapter["title"],
                    "sources": [{**r, "source": "curated_catalog", "status": "catalog_only"}
                                for r in relevant_refs(chapter)], "errors": [],
                    "evidence_scope": "curated catalog only"}
    if write and (refresh or not paths["draft"].exists()):
        if author is None:
            from .crew import generate
            author = generate
        content = ensure_reference_section(author(chapter, evidence_bundle=evidence), evidence["sources"])
        paths["draft"].parent.mkdir(parents=True, exist_ok=True)
        paths["draft"].write_text(content, encoding="utf-8")
    if not paths["draft"].exists():
        return {"state": "researched", "chapter": chapter["number"], "evidence": str(paths["evidence"])}
    report = verify_chapter(paths["draft"].read_text(encoding="utf-8"), chapter, evidence)
    save_report(report, paths["report"])
    return {"state": "review_ready" if report["passed_gate"] else "needs_revision",
            "chapter": chapter["number"], "draft": str(paths["draft"]),
            "report": str(paths["report"]), "issues": report["issues"],
            "review_warnings": report["review_warnings"]}
