"""Approved-only book assembly and optional Pandoc exports."""
import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from .catalog import syllabus


def assemble_approved(output, *, require_complete=False):
    out, spec = Path(output), syllabus()
    chosen, missing, pages = [], [], [
        f"# {spec['title']}", f"*{spec['subtitle']}*", f"Edition: {spec['edition']}", ""]
    for part in spec["parts"]:
        content = []
        for ch in part["chapters"]:
            path = out / "approved" / f"chapter_{ch['number']:02d}.md"
            if not path.is_file():
                missing.append(ch["number"])
                continue
            content.append(path.read_text(encoding="utf-8"))
            chosen.append(ch["number"])
        if content:
            pages.extend([f"# Part {part['number']}: {part['title']}", *content, "\n---\n"])
    if not chosen:
        raise ValueError("No approved chapters; nothing to publish")
    if require_complete and missing:
        raise ValueError(f"Missing {len(missing)} approved chapters")
    folder = out / "books"
    folder.mkdir(parents=True, exist_ok=True)
    content = "\n\n".join(pages)
    dest = folder / "principal_ai_engineers_handbook.md"
    temp = dest.with_suffix(".md.tmp")
    temp.write_text(content, encoding="utf-8")
    temp.replace(dest)
    manifest = {"built_at_utc": datetime.now(timezone.utc).isoformat(),
                "status": "partial" if missing else "complete", "chapters": chosen,
                "missing_chapters": missing, "sha256": hashlib.sha256(content.encode()).hexdigest()}
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return dest, manifest


def export_book(manuscript, format, *, pdf_engine="xelatex"):
    if format not in ("docx", "pdf", "epub"):
        raise ValueError("format must be docx, pdf or epub")
    if not shutil.which("pandoc"):
        raise RuntimeError("Pandoc is required to export")
    manuscript = Path(manuscript)
    if not manuscript.is_file():
        raise FileNotFoundError(manuscript)
    target = manuscript.with_suffix("." + format)
    command = ["pandoc", str(manuscript), "-o", str(target), "--standalone", "--toc"]
    if format == "pdf":
        command += ["--pdf-engine", pdf_engine]
    result = subprocess.run(command, capture_output=True, text=True, timeout=180)
    if result.returncode != 0 or not target.is_file():
        raise RuntimeError("Pandoc export failed: " + result.stderr[-2000:])
    return target
