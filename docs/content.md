# Content and citations

How the authored entries in `content/` are written and validated, and the open-access-only citation rules and
tooling behind them. Back to the [README](../README.md).

## Authoring content

Content lives as JSON in `content/data/<kind>/<id>.json`, validated by the zod schemas in `content/schema/` (`structure`, `cranial-nerve`, `pathway`, `syndrome`, `topic`, `glossary`, `quiz`). Entries are written with the Python helpers in `tools/author/` (`lib.py` for structures and topics, `synlib.py` for syndromes, `corlib.py`/`tractlib.py` for mesh-backed parcels and tracts) and the batch scripts `batchNN_*.py`; `node scripts/content/build.ts` validates, checks cross-links, word minimums, spelling, an 11-word-shingle overlap check against the private reference corpus, and bundles.

Rules: American spelling; every non-glossary entry carries at least one open-access citation; syndromes must state the crossing/side logic; imaging block mandatory; no figure or table references; all quiz vignettes original.

## Sources and citations

Counts today: **657 sources — 606 StatPearls chapters, 49 open-access journal articles (PubMed Central, plus one bioRxiv preprint), 1 openly licensed textbook page and 1 documentation page — carrying 2387 citations across 825 entries** (1–6 refs each; 2267 of them name a section that was read from the live article). No printed textbook is referenced anywhere in the shipped atlas. Two method papers whose journal versions are paywalled are cited through free copies instead: the VENAT venous atlas (Huck 2019) through its bioRxiv preprint, and the PAM50 spinal cord template (De Leener 2018) through the Spinal Cord Toolbox documentation page that describes it.

Citations are open access only. A citation is `{"ref": "<id>", "section": "...", "note": "..."}` and `ref` names a file in `content/bibliography/<ref>.json`; the build fails on an unknown ref, and `npm run citations:check` fails on any citation that is not in this form, on an unverified bibliography entry and on a bibliography entry nothing cites.

A bibliography entry records the title, authors, year, container, canonical free full-text URL, the accession that identifies it (`nbk` for the NCBI Bookshelf, `pmcid`/`doi`/`pmid` for articles), the licence and `verified: true`. **`verified: true` is only ever written by a tool from live source metadata** — never by hand:

| Type | What it is | Added with |
|---|---|---|
| `statpearls` | peer-reviewed StatPearls chapter on the NCBI Bookshelf (`https://www.ncbi.nlm.nih.gov/books/NBK…/`) | `tools/cite/statpearls.py`, in bulk by `tools/cite/migrate.py` |
| `journal` | open-access article, stored with its PMCID and the PMC URL | `tools/cite/oa.py --pmcid PMC…` |
| `book` / `web` | openly licensed textbook or reference page (OpenStax *Anatomy and Physiology 2e*, UTHealth *Neuroscience Online*, Radiopaedia) with a specific section | `tools/cite/oa.py --web <url> …` (only written after the URL returns HTTP 200) |

The citation tooling lives in `tools/cite/`:

```bash
python3 tools/cite/catalog.py --terms-from-content   # harvest the StatPearls chapter catalog (cached in reference/)
python3 tools/cite/migrate.py                        # dry run: per-entry plan and match-quality table
python3 tools/cite/migrate.py --unmatched            # entries needing a manual mapping decision, with candidates
python3 tools/cite/migrate.py --apply                # write bibliography entries and rewrite every citations array
python3 tools/cite/statpearls.py --search "phrenic nerve"
python3 tools/cite/oa.py --pmc-search "claustrum connectivity review"
```

`migrate.py` derives search terms from each entry's name, synonyms, id and kind, queries the NCBI E-utilities (`esearch`/`esummary`, ≤3 requests/s, every response cached under the gitignored `reference/`), scores candidate chapters with a rarity-weighted title match, and adds system- and lobe-level chapters as supporting refs. Chapter section names (`"Structure and Function"`, `"Clinical Significance"`, …) are read from the live chapter, never guessed. Decisions the automatic pass cannot make are recorded by hand in `tools/cite/mapping.json`. Re-running `migrate.py --apply` is safe: entries whose citations are already refs are left untouched.

`tools/ref_*.py` and `tools/refcorpus.py` build an **optional private text corpus** under `reference/` used only by the build's 11-word-shingle plagiarism check (`scripts/content/plagiarism.ts`). Nothing from it is shipped, and the check is skipped when `reference/` is absent.
