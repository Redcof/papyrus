"""Load the fixed syllabus and verified reference seed catalog."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def syllabus():
    return json.loads((ROOT / "syllabus.json").read_text(encoding="utf-8"))


def references():
    return json.loads((ROOT / "references.json").read_text(encoding="utf-8"))


def chapters():
    for part in syllabus()["parts"]:
        for ch in part["chapters"]:
            yield {**ch, "part_number": part["number"], "part_title": part["title"]}


def get_chapter(number):
    return next((c for c in chapters() if c["number"] == number), None)


def relevant_refs(chapter):
    p = chapter["part_number"]
    tags = {
        1: {"statistics", "ml", "product"}, 2: {"ml", "genai"},
        3: {"cv", "ml"}, 4: {"genai", "ml"}, 5: {"rag", "genai"},
        6: {"agents", "aws", "rag"}, 7: {"mlops", "data", "systems"},
        8: {"systems", "mlops"}, 9: {"product", "cv", "statistics"},
        10: {"leadership", "systems", "mlops"}, 11: {"ml", "systems", "agents"},
    }[p]
    return [r for r in references() if tags.intersection(r["tags"])]
