"""Deterministic chapter verification. Does not execute LLM-generated code."""
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from .quality import inspect

CITE = re.compile(r'\[@([\w-]+)\]')
PYTHON = re.compile(r'```python\s*\n(.*?)\n```', re.S)
MERMAID = re.compile(r'```mermaid\s*\n(.*?)\n```', re.S)


def verify_chapter(markdown, chapter, bundle, *, run_mermaid=False):
    refs = [{"id": source["id"]} for source in bundle["sources"]]
    static = inspect(markdown, chapter, refs)
    issues = list(static["issues"])
    used = set(CITE.findall(markdown))
    sources = {r["id"]: r for r in bundle["sources"]}
    if not used:
        issues.append("No cited sources")
    unsupported = used - sources.keys()
    if unsupported:
        issues.append("Unknown citations: " + ", ".join(sorted(unsupported)))
    warnings = []
    if any(sources[c]["status"] in ("catalog_only", "lookup_failed") for c in used & sources.keys()):
        warnings.append("Some sources are catalog-only; human source review required")
    if any(sources[c]["source"] == "openalex" for c in used & sources.keys()):
        warnings.append("OpenAlex abstract/metadata does not verify cited claims")
    if bundle.get("errors"):
        warnings.append("Research lookup errors require inspection")
    graphs = []
    for idx, diagram in enumerate(MERMAID.findall(markdown), 1):
        state = "not_rendered"
        if run_mermaid:
            if not shutil.which("mmdc"):
                issues.append("Mermaid CLI (mmdc) not installed")
            else:
                import tempfile
                with tempfile.TemporaryDirectory() as directory:
                    src, dst = Path(directory) / "diagram.mmd", Path(directory) / "diagram.svg"
                    src.write_text(diagram, encoding="utf-8")
                    try:
                        result = subprocess.run(["mmdc", "-i", str(src), "-o", str(dst)],
                                                capture_output=True, text=True, timeout=30)
                        state = "rendered" if result.returncode == 0 and dst.exists() else "failed"
                    except subprocess.TimeoutExpired:
                        state = "timeout"
                    if state != "rendered":
                        issues.append(f"Mermaid diagram {idx} failed: {state}")
        graphs.append({"block": idx, "status": state})
    return {"chapter": chapter["number"], "sha256": hashlib.sha256(markdown.encode()).hexdigest(),
            "passed_static_checks": static["passed_static_checks"], "passed_gate": not issues,
            "issues": issues, "review_warnings": warnings, "citations": sorted(used),
            "code_blocks": len(PYTHON.findall(markdown)), "diagrams": graphs,
            "code_executed": False, "claims_fact_checked": False, "human_review_required": True}


def save_report(report, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return path


def approval_allowed(markdown, report):
    return bool(report.get("passed_gate")) and hashlib.sha256(markdown.encode()).hexdigest() == report.get("sha256")
