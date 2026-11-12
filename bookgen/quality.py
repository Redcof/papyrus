"""Static checks only: NEVER execute untrusted model-generated code."""
import ast
import re

CODE = re.compile(r"```([a-zA-Z0-9_+-]*)\s*\n(.*?)\n```", re.DOTALL)
CITATION = re.compile(r"\[@([A-Za-z0-9_-]+)\]")
HEADINGS = [
    "Learning Objectives", "Foundations", "Worked Example", "Implementation",
    "Architecture and Flowcharts", "Production Trade-offs", "Interview Questions",
    "Exercises", "References",
]


def inspect(markdown: str, chapter: dict, allowed_refs: list[dict]) -> dict:
    problems = []
    headings = re.findall(r"^##\s+(.+)$", markdown, re.MULTILINE)
    for heading in HEADINGS:
        if not any(h.casefold().startswith(heading.casefold()) for h in headings):
            problems.append(f"Missing section: {heading}")
    if chapter["type"] == "technical" and not re.search(r"^##\s+Mathematical Derivation", markdown, re.MULTILINE):
        problems.append("Missing Mathematical Derivation section")
    if chapter["type"] == "technical" and "$$" not in markdown and "\\[" not in markdown:
        problems.append("No display mathematics found")
    fences = list(CODE.finditer(markdown))
    if not any(f.group(1).lower() == "mermaid" for f in fences):
        problems.append("No Mermaid diagram found")
    if not any(f.group(1).lower() in {"python", "cpp", "sql", "bash"} for f in fences):
        problems.append("No executable-language code fence found")
    for i, match in enumerate(fences, 1):
        if match.group(1).lower() == "python":
            try:
                ast.parse(match.group(2))
            except SyntaxError as exc:
                problems.append(f"Python block {i} syntax error at line {exc.lineno}: {exc.msg}")
    ids = {r["id"] for r in allowed_refs}
    used = set(CITATION.findall(markdown))
    if not used:
        problems.append("No in-text [@reference_id] citations found")
    for unknown in sorted(used - ids):
        problems.append(f"Unrecognized citation: {unknown}")
    if markdown.count("```") % 2:
        problems.append("Unbalanced fenced code blocks")
    return {"passed_static_checks": not problems, "issues": problems, "citations": sorted(used), "words": len(markdown.split()), "code_blocks": len(fences)}


def ensure_reference_section(markdown: str, refs: list[dict]) -> str:
    """Replace references section using only catalog entries actually cited."""
    used = set(CITATION.findall(markdown))
    clean = re.split(r"^## References\s*$", markdown, maxsplit=1, flags=re.MULTILINE)[0].rstrip()
    items = [f"- **[@{r['id']}]** {r['citation']} {r['url']}" for r in refs if r["id"] in used]
    return clean + "\n\n## References\n\n" + ("\n".join(items) if items else "*No supported citations supplied; requires research review.*") + "\n"
