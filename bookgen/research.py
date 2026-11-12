"""Bibliographic research from Crossref and OpenAlex; metadata is NOT claim verification."""
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .catalog import relevant_refs

DOI = re.compile(r'(?:https?://(?:dx\.)?doi\.org/)?(10\.\d{4,9}/\S+)', re.I)
USER_AGENT = "Papyrus/0.2 (+https://github.com/Redcof/papyrus)"


def _get_json(url, *, opener=urlopen, attempts=3):
    if not url.startswith(("https://api.crossref.org/", "https://api.openalex.org/")):
        raise ValueError("Only allowed metadata APIs may be queried")
    for attempt in range(attempts):
        try:
            request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            with opener(request, timeout=20) as response:
                payload = response.read(2_000_001)
            if len(payload) > 2_000_000:
                raise ValueError("Response exceeds 2MB")
            return json.loads(payload)
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == attempts - 1:
                raise
        except URLError:
            if attempt == attempts - 1:
                raise
        time.sleep(min(2 ** attempt, 4))


def _text(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', value or '')).strip()


def _abstract(index):
    if not index:
        return ""
    words = [(p, word) for word, positions in index.items() for p in positions]
    return " ".join(word for _, word in sorted(words))[:3500]


def research_chapter(chapter, *, max_discovered=5, fetch=_get_json):
    sources, errors = [], []
    for ref in relevant_refs(chapter):
        row = {"id": ref["id"], "title": ref["citation"], "url": ref["url"],
               "source": "curated_catalog", "status": "catalog_only", "metadata": {}}
        match = DOI.search(ref["url"])
        if match:
            try:
                value = fetch("https://api.crossref.org/works/" + quote(match.group(1).rstrip(".,;)"), safe="/"))["message"]
                row["source"] = "crossref"
                row["status"] = "doi_metadata_verified"
                row["metadata"] = {"doi": value.get("DOI"), "title": _text((value.get("title") or [""])[0]),
                                   "year": (value.get("published", {}).get("date-parts") or [[None]])[0][0],
                                   "publisher": value.get("publisher", "")}
            except (KeyError, ValueError, HTTPError, URLError, TimeoutError) as exc:
                errors.append({"source": ref["id"], "error": str(exc)[:200]})
                row["status"] = "lookup_failed"
        sources.append(row)
    query = {"search": chapter["title"], "per-page": min(max(max_discovered, 1), 20),
             "select": "id,doi,title,publication_year,abstract_inverted_index"}
    if os.getenv("OPENALEX_API_KEY"):
        query["api_key"] = os.environ["OPENALEX_API_KEY"]
    try:
        data = fetch("https://api.openalex.org/works?" + urlencode(query))
        for item in data.get("results", []):
            url = item.get("doi") or item.get("id") or ""
            sources.append({"id": "oa_" + hashlib.sha256(url.encode()).hexdigest()[:12],
                            "title": item.get("title", ""), "url": url, "source": "openalex",
                            "status": "metadata_retrieved",
                            "metadata": {"year": item.get("publication_year"), "doi": item.get("doi"),
                                         "abstract": _abstract(item.get("abstract_inverted_index"))}})
    except (KeyError, ValueError, HTTPError, URLError, TimeoutError) as exc:
        errors.append({"source": "openalex", "error": str(exc)[:200]})
    return {"chapter": chapter["number"], "topic": chapter["title"],
            "researched_at_utc": datetime.now(timezone.utc).isoformat(),
            "evidence_scope": "bibliographic metadata/abstract only; NOT full-text claim verification",
            "sources": sources, "errors": errors}


def save_bundle(bundle, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_bundle(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
