# Contributing

Thanks for looking. This is the Clinical Neuroanatomy Atlas — a browser-based 3D
atlas built from open MNI-space datasets, with original prose cited entirely to
open-access sources. It is maintained by Batuhan Ayci
(<batuhanayci@gmail.com>).

Code is Apache-2.0; the authored content in `content/` and the generated data in
`public/data/` are CC BY-SA 4.0. By opening a pull request you agree that your
contribution ships under those licences.

Read [`README.md`](README.md) first — it explains what the atlas is, how the
pipeline is put together and why the meshes are where they are. This file is
about working on it. Security, licence and redistribution reports go to
[`SECURITY.md`](SECURITY.md).

---

## Prerequisites

| | |
|---|---|
| **Node 22+ and npm** | the app, the content build and every `npm run` check. `package-lock.json` is committed — use `npm ci`, not `npm install`. |
| **[uv](https://docs.astral.sh/uv/)** | the Python pipeline in `pipeline/` is a uv project (`requires-python = ">=3.12,<3.13"`). You only need it if you are regenerating data. |
| **Python 3.12+** | the standalone tools under `tools/` (`tools/i18n/prose.py`, `tools/cite/*.py`). `prose.py` is pure standard library — plain `python3` is enough, no venv. |
| **Playwright chromium** | `npx playwright install chromium`, for `npm run e2e`. |
| **Blender `bpy`** | only if you touch the Z-Anatomy export (`blender/.venv`, see the README). |

## Getting the generated data

**A fresh clone has no `public/data/`.** Meshes, MRI volumes, label tables and
`manifest.json` are built by the pipeline from downloaded source atlases and are
gitignored, because they are large and fully regenerable. The app will not boot
without them: `manifest.json` 404s and the scene never loads.

What *does* work in a bare clone, straight after `npm ci`: `npm run typecheck`,
`npm run content:validate`, `npm run citations:check`, `npm run notice --
--check`, `npm run build`, six of the eight unit test files (five pass, one skips itself),
and `python3 tools/i18n/prose.py check`. That is exactly the set the CI workflow
runs. The two remaining test files — `tests/public-edition.test.ts` and
`tests/spine-lut.test.ts` — read `public/data/` when they are imported, so plain
`npm test` fails without the data. Everything else needs it too.

To build it:

```bash
cd pipeline && uv sync && cd ..
uv run --project pipeline atlas-build     # download → volumes → register → meshes → labels → manifest → QA
node scripts/check-data.ts                # integrity check over what was produced
npm run content                           # bundle content/ into public/data/content.json
npm run dev                               # http://localhost:5173
```

This downloads several GB and takes a while. Individual steps and the optional
extras (Z-Anatomy, the public-edition cord MRI, the manually downloaded
Brainstem Navigator toolkit) are documented under *Running the app* in the
README. If you only want to work on text, you can skip the pipeline entirely and
use the content checks — they do not need the data.

## The two branches

The project ships in two editions, and they are two branches.

| Branch | Edition | Contains |
|---|---|---|
| `main` | **public** | only what may be redistributed: Apache-2.0 code, CC BY-SA 4.0 data and content. |
| `private` | **private** | the same tree, built with four restricted datasets as well. |

The two branches carry the same files. What differs is what you are allowed to
build and commit on them, and that is enforced, not just documented: the
restricted datasets sit in the `restricted` download group, which
`atlas-download` fetches only on `private` or with `ATLAS_ALLOW_RESTRICTED=1`,
and `npm run check-tree` fails on `main` if one of them is put back into a
default group. Which edition a build *is* follows from the data present, never
from a flag: with no restricted data, `atlas-manifest` writes only
`manifest.json` (public); with it, it also writes `manifest.private.json`.

The restricted datasets are Harvard-Oxford (FSL, non-commercial), the
Diedrichsen cerebellar atlas (CC BY-NC 3.0), the Brainstem Navigator
(non-commercial, and its terms forbid passing derived files outside your
organisation) and the PAM50 spinal cord template (ships no licence file at all).
They are flagged `nc: true` / `no_redistribution: true` in
`pipeline/config/sources.yaml`, and `filter_public()` in
`pipeline/atlas_pipeline/manifest.py` drops everything derived from them. That
flag is the only mechanism — nothing is special-cased by name, so if the licence
picture changes you change the flag and both editions follow.

**The plain names are the public edition.** In `public/data/`, `manifest.json`,
`content.json`, `search-index.json` and `content.tr.json` are always the
redistributable bundles; the private edition, where it exists, is
`manifest.private.json` and friends. So `npm run dev` and `npm run build` are
public by default on any machine, and the private edition is what you ask for:
`npm run dev:private`, `npm run build:private`.

**How work flows.**

- **Develop on `main`.** Almost everything — code, content, translations,
  tooling, pipeline logic — belongs there, including the pipeline code that
  builds the restricted meshes. It is the *data* that is restricted, not the
  code that would process it.
- `main` → `private` by merge or rebase, routinely, so `private` is never far
  behind.
- Anything developed on `private` that is not itself restricted must be
  **cherry-picked back to `main`**. Do not let a fix live only on `private`.
- Never merge `private` → `main`.

**Never committed on either branch** (see `.gitignore`):

- `source/` — two clinical neuroanatomy textbook PDFs, used only as writing
  references. They are not redistributable and nothing derived from their
  wording may enter the repo.
- `reference/` — the derived private text corpus and the API caches.
- `pipeline/raw/`, `pipeline/work/` — downloads and intermediates.
- `public/data/`, `dist/`, `dist-private/` — generated output.
- `pipeline/qa/report.json` on `main` — the QA record of a *private* build. It carries no
  geometry, only counts and gate results, so `private` keeps it; the public branch does not.

Two guards enforce this; run both before you push, and definitely before a
release:

```bash
npm run check-tree      # fails if a restricted source, a private path or a data blob is committed
npm run build           # builds dist/ and runs scripts/check-public.ts over it
```

`npm run check-tree` guards the *repository*; `npm run build` guards the
*build*, and it is the default build precisely so that the gate is not
something you have to remember. `tests/public-edition.test.ts` re-implements the exclusion rule in
TypeScript and asserts it against the real private manifest, so the Python and
TypeScript versions cannot drift apart. None of the three can run in CI (they
need the generated data), which is why they are your job locally.

## Adding or editing content

Content is authored JSON: `content/data/<kind>/<id>.json`, one file per entry,
validated by the zod schemas in `content/schema/`. The kinds are `structure`,
`cranial-nerve`, `pathway`, `syndrome`, `topic`, `glossary` and `quiz`.

Entries are usually written with the Python helpers in `tools/author/`
(`lib.py` for structures and topics, `synlib.py` for syndromes,
`corlib.py`/`tractlib.py` for mesh-backed parcels and tracts) and the batch
scripts next to them, but editing the JSON by hand is perfectly fine for a fix.

**Rules.** The build enforces most of these; the rest are review criteria.

- **American spelling** in content (`color`, `gray matter`, `edema`). Note that
  the README, the commit log and this file use British spelling — the American
  rule applies to `content/` only.
- **Every non-glossary entry carries at least one open-access citation.** Open
  access means a reader can get the full text for free: StatPearls chapters on
  the NCBI Bookshelf, articles in PubMed Central, openly licensed pages. **Never
  a printed textbook**, and never a paywalled article — if the only version you
  can find is behind a paywall, find a free equivalent or leave the claim out.
- **Syndromes must state the crossing/side logic** explicitly — which deficits
  are ipsilateral, which contralateral, and why, in terms of where the tract
  decussates. Prefer `ipsilateral`/`contralateral` to "same side".
- **The imaging block is mandatory** on syndromes: modality, sequence, what you
  actually see.
- **No figure or table references** ("see Figure 4-2") — there are no figures.
- **Quiz vignettes must be original.** The build runs an 11-word-shingle overlap
  check against the private reference corpus when `reference/` is present.
- **Do not casually change MNI coordinates or mesh ids.** They are the join
  between the text and the geometry; a wrong coordinate puts a lesion marker
  inside the wrong structure. If a coordinate is wrong, say in the pull request
  how you checked the new one.

**Citations.** A citation is `{"ref": "<id>", "section": "...", "note": "..."}`
and `ref` names a file in `content/bibliography/<ref>.json`. Add bibliography
entries with the tools, never by hand:

```bash
python3 tools/cite/statpearls.py --search "phrenic nerve"
python3 tools/cite/oa.py --pmcid PMC1234567
python3 tools/cite/oa.py --pmc-search "claustrum connectivity review"
```

`verified: true` is only ever written by a tool from live source metadata.
Section names are read from the live chapter, never guessed. Bibliography files
are marked `linguist-generated` in `.gitattributes` and are collapsed in pull
requests for exactly this reason.

**Running the content build:**

```bash
npm run content:validate   # schemas, cross-links, word minimums, spelling, coverage (no write)
npm run citations:check    # citation form, unverified entries, uncited entries
npm run content:report     # per-kind counts and gaps
npm run content            # write public/data/content.json, search-index.json, content.tr.json
npm run content:private    # the same for the private edition (.private.json), where it exists
```

## Turkish translations

The interface strings live in `src/i18n/en.ts` and `src/i18n/tr.ts` (the Turkish
table is typed against the English one, so a missing key fails
`npm run typecheck`). The clinical prose is translated as **overlays**:

```
content/i18n/tr/<kind>/<id>.json
{ "id": …, "kind": …, "lang": "tr",
  "source": "<sha1 of the English strings of the entry>",
  "fields": { "<flattened path>": "<Turkish>" } }
```

`fields` maps a flattened path of the English entry (`deficits[2].sign`,
`anatomy.subdivisions[0].note`) to its translation. Every translatable path must
be present; identifiers, enumerations, citations, mesh ids and MNI numbers are
never in an overlay, and neither is the `name` of a structure, nerve or pathway
(Turkish mode shows the Latin term).

```bash
python3 tools/i18n/prose.py extract [--words 12000] [--kinds syndromes,topics]
python3 tools/i18n/prose.py check [--strict]
python3 tools/i18n/prose.py status
```

`extract` writes translator task files under the gitignored
`reference/i18n-tasks/` together with the style guide,
[`tools/i18n/STYLE-tr.md`](tools/i18n/STYLE-tr.md) — read it before translating
anything. The short version: Latin structure names, Turkish clinical vocabulary,
every sentence translated, nothing summarised, markdown and link targets
preserved.

**The `source` hash is the part that catches people out.** Each overlay pins a
hash of the English strings it was made from. **Editing an English entry
therefore invalidates its Turkish overlay**, and `prose.py check` reports it as
stale — so a content-only pull request can fail on the translation check and
nowhere else. When you edit English prose, either update the Turkish alongside
it and re-pin the hash, or say in the pull request that the overlay needs
redoing. In the app a stale or missing translation shows an *English* tag rather
than wrong Turkish, so a temporarily stale overlay is safe, just visible.

Structure names come from a separate terminology table
(`tools/i18n/terms.py fetch | table | show | apply`, reviewed in
`content/i18n/review/terms-review.csv`, whose `decision` column is the
reviewer's and survives regeneration). `fetch` needs the cache under
`reference/` and network access, so it is a maintainer job, not a routine one.

## Checks

The full local suite, in order. Copy-paste it:

```bash
npm run check-tree                                # no restricted/private/generated files committed
npm run typecheck
npm test                                          # vitest
npm run content:validate
npm run citations:check
node scripts/check-data.ts                        # needs public/data/
npm run notice -- --check                         # NOTICE is generated; never edit it by hand
uv run --project pipeline atlas-qa                # pipeline data gates; needs pipeline/work/
npx playwright install chromium && npm run e2e    # browser smoke tests against the dev server
npm run build                                     # builds dist/ and runs the redistribution gate over it
python3 tools/i18n/prose.py check                 # Turkish overlays against the English entries
```

`.github/workflows/checks.yml` runs the subset that works without
`public/data/`. Everything else is on you locally — including, importantly,
`npm run build` and `node scripts/check-data.ts`.

## Commit messages

Read `git log`; the house style is consistent and unusual enough to be worth
stating.

- **One long, descriptive subject line.** The median subject in this repo is
  about 100 characters and they run to 400. Say what changed and what it means,
  not just where.
- Sentence case, no trailing period. **No Conventional Commits prefixes** —
  no `feat:`, `fix:`, `chore:`, no scope parentheses.
- Usually `Area: what changed`, with further clauses separated by semicolons.
- Add a body paragraph when the *why* is not obvious from the subject —
  a decision made, a trade-off, a number that justifies the change.
- Numbers and identifiers over adjectives: counts, file paths, tolerances.

Real examples from the log:

```
Panels: citations casts against the typed entry

Not-for-clinical-use disclaimer in the README and About panel; BodyParts3D
licence record updated to CC BY 4.0 with the share-alike chain verified

The p shortcut peels at the slice last toggled with a / c / s, not only the
axial one
```

Commit prose uses British spelling ("licence", "normalised") — only `content/`
is American.

## What not to contribute

- **Text derived from a textbook.** Not paraphrased, not "reworded", not
  translated. The prose here is original and cited to sources anyone can open
  for free; anything traceable to `source/` cannot ship. The build's shingle
  overlap check exists to catch this and a hit is a hard stop, not a warning.
- **Restricted atlas data on `main`** — Harvard-Oxford, Diedrichsen, Brainstem
  Navigator or PAM50 files, or *anything derived from them*: meshes, volumes,
  label tables, manifest rows, screenshots of them. The Brainstem Navigator's
  terms specifically forbid derived files leaving the organisation.
- **Figures, tables, diagrams or photographs from books**, and images whose
  licence you cannot name.
- **Citations to paywalled or printed sources**, however authoritative.
- **Generated files.** `NOTICE`, `public/data/`, `dist/`, `dist-private/`,
  `content/coverage.json` and the terminology review tables are written by
  tools. Change the tool or the source, not the output.
- **Large binaries.** Meshes, volumes and screenshots are regenerable; keep them
  out of git history, where they are permanent.
- **Clinical advice.** This is an educational reference and says so. Entries
  describe and localise; they do not tell anyone what to do to a patient.

If you are not sure whether something is redistributable, ask before you commit
it — email rather than opening a public issue, as `SECURITY.md` explains.
