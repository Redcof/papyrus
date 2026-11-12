from bookgen.catalog import chapters, references, get_chapter
from bookgen.quality import inspect, ensure_reference_section


def test_syllabus_has_60_unique_chapters():
    items = list(chapters())
    assert len(items) == 60
    assert [c["number"] for c in items] == list(range(1, 61))
    assert get_chapter(31)["title"].startswith("Tool Calling") is False  # 31 is Advanced RAG


def test_reference_catalog_ids_unique():
    ids = [r["id"] for r in references()]
    assert len(ids) == len(set(ids))


def test_static_checker_detects_unknown_source_and_bad_python():
    ch = get_chapter(1)
    content = "# Chapter 1\n\n## References\n\n[@unknown]\n\n```python\ndef broken(:\n    pass\n```\n"
    report = inspect(content, ch, references())
    assert not report["passed_static_checks"]
    assert any("Unrecognized citation" in issue for issue in report["issues"])
    assert any("syntax error" in issue for issue in report["issues"])


def test_bibliography_builder_only_uses_cited_sources():
    refs = references()
    content = "# Example\n\nSee [@vaswani2017].\n\n## References\nold"
    result = ensure_reference_section(content, refs)
    assert "Attention Is All You Need" in result
    assert "old" not in result
