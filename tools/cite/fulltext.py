#!/usr/bin/env python3
"""Full-text StatPearls search (db=books, all fields) — finds chapters that *discuss* a subject whose
name never appears in a chapter title (claustrum -> Insular Cortex, reticulospinal -> Extrapyramidal System).
Results are candidates for the manual mapping pass, never applied automatically."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ncbi

ROOT = Path(__file__).resolve().parents[2]
STORE = ROOT / "reference" / "fulltext-candidates.json"
_data: dict[str, list[dict]] | None = None


def load() -> dict[str, list[dict]]:
    global _data
    if _data is None:
        _data = json.loads(STORE.read_text()) if STORE.exists() else {}
    return _data


def warm(names: list[str]) -> None:
    d = load()
    todo = [n for n in dict.fromkeys(names) if n not in d]
    if not todo:
        return
    ncbi.prefetch([ncbi.search_url("books", f'"{n}" AND statpearls[book]', 8) for n in todo], progress="fulltext")
    for i, n in enumerate(todo, 1):
        ids = ncbi.esearch("books", f'"{n}" AND statpearls[book]', 8)
        recs = [r for r in (ncbi.parse_book(x) for x in ncbi.esummary("books", ids)) if r and r["nbk"]]
        d[n] = [{"nbk": r["nbk"], "title": r["title"]} for r in recs]
        if i % 25 == 0:
            print(f"  fulltext {i}/{len(todo)}", file=sys.stderr, flush=True)
    STORE.write_text(json.dumps(d, indent=1, ensure_ascii=False))


def candidates(name: str) -> list[dict]:
    return load().get(name, [])


if __name__ == "__main__":
    warm(sys.argv[1:])
    for n in sys.argv[1:]:
        print(n, candidates(n))
