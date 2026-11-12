"""Offline validation of pipeline behavior; no LLM calls or network needed."""
import json

import pytest

from bookgen.catalog import get_chapter
from bookgen.pipeline import run_chapter, chapter_artifacts
from bookgen.publishing import assemble_approved, export_book
from bookgen.research import research_chapter
from bookgen.verification import approval_allowed, verify_chapter


CHAPTER = """# Chapter 1: Probability, Distributions and Bayesian Reasoning
## Learning Objectives
Understand probabilities.
## Foundations
A basic fact [@bishop2006].
## Mathematical Derivation
$$P(A|B)=P(B|A)P(A)/P(B)$$
## Worked Example
Worked example.
## Implementation
```python
print("Hello, world")
```
## Architecture and Flowcharts
```mermaid
flowchart LR
A[Data] --> B[Model]
```
## Production Trade-offs
Trade-offs.
## Interview Questions
Questions.
## Exercises
Exercises.
## References
[@bishop2006]
"""


def evidence(ch, **kwargs):
    return {"chapter": ch["number"], "sources": [
        {"id": "bishop2006", "status": "doi_metadata_verified", "title": "Bishop", "url": "https://example.org"}],
        "errors": []}


def author(ch, evidence_bundle=None):
    return CHAPTER


def test_resumable_pipeline(tmp_path):
    ch = get_chapter(1)
    result = run_chapter(ch, tmp_path, research_func=evidence, author=author)
    assert result["state"] == "review_ready"
    result = run_chapter(ch, tmp_path,
                         research_func=lambda *args, **kwargs: 1 / 0,
                         author=lambda *args, **kwargs: 1 / 0)
    assert result["state"] == "review_ready"
    report = json.loads(chapter_artifacts(tmp_path, ch)["report"].read_text())
    assert report["code_executed"] is False
    assert approval_allowed(chapter_artifacts(tmp_path, ch)["draft"].read_text(), report)


def test_unknown_citation_blocks_approval():
    ch = get_chapter(1)
    report = verify_chapter(CHAPTER.replace("bishop2006", "made_up"), ch, evidence(ch))
    assert not report["passed_gate"]


def test_research_with_mock_api():
    def fetch(url):
        if "openalex" in url:
            return {"results": [{"title": "A paper", "id": "https://openalex.org/W1",
                                 "doi": None, "publication_year": 2025,
                                 "abstract_inverted_index": {"Test": [0]}}]}
        return {"message": {"DOI": "10.1234/test", "title": ["Test"], "published": {"date-parts": [[2023]]}}}
    result = research_chapter(get_chapter(1), fetch=fetch)
    assert any(r["source"] == "openalex" for r in result["sources"])


def test_publish_rejects_empty(tmp_path):
    with pytest.raises(ValueError):
        assemble_approved(tmp_path)
    approved = tmp_path / "approved"
    approved.mkdir()
    (approved / "chapter_01.md").write_text(CHAPTER)
    manuscript, manifest = assemble_approved(tmp_path)
    assert manuscript.is_file() and manifest["status"] == "partial"
    with pytest.raises(ValueError):
        assemble_approved(tmp_path, require_complete=True)


def test_export_rejects_invalid_format(tmp_path):
    with pytest.raises(ValueError):
        export_book(tmp_path / "missing.md", "html")
