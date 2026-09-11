# Working on this repository

A browser-based 3D atlas of clinical neuroanatomy: meshes in MNI152 space, synchronised MRI slices, and
authored clinical content in English and Turkish. Vite + TypeScript + three.js in `src/`, a Python pipeline in
`pipeline/`, and the prose as JSON in `content/`.

This file is for anyone — human or agent — setting the project up or changing it. [README.md](README.md) is the
tour; this is the operating manual. The traps below are the ones that actually cost time.

## Setting up

```bash
npm ci
npm run data           # 48 MB from the v1.0.1 release into public/data/, SHA-256 checked
npm run dev            # http://localhost:5173
```

**The atlas data is not in this repository and must never be committed.** `public/data/` is 63 MB of generated
meshes, MRI volumes and label tables; it is gitignored, and `npm run check-tree` fails if it is ever tracked.
Skip `npm run data` and the app starts and tells you what to run — it does not hang or throw.

To generate the data instead of downloading it, see [docs/pipeline.md](docs/pipeline.md). It needs `uv`,
downloads several GB, and takes a long time. You almost never need it: reach for it only when changing how the
meshes or volumes are built.

## Rules that are not negotiable

1. **Never commit generated or private data.** Not `public/data/`, `dist/`, `dist-private/`, `pipeline/raw/`,
   `pipeline/work/`, `source/`, `reference/`, `qa/shots/`, and no mesh, volume or archive. `npm run check-tree`
   enforces this and runs as a pre-commit hook (`npm run hooks:install`) and in CI.
2. **Never weaken `scripts/check-public.ts` or `scripts/check-tree.ts` to make something pass.** They are the
   whole licence guarantee. If one fires, it is describing a real problem — fix the problem.
3. **`dist-private/` must never be published, deployed or copied anywhere shared.** Only `npm run build`
   output is redistributable, and only because `check-public` certifies it.
4. **The `private` branch and the `v1.0.0-private` tag stay local.** Never push them. Work happens on `main`
   and is rebased onto `private`; never merge `private` into `main`.
5. **The exclusion of the four restricted datasets is unconditional, and "this project is non-commercial" is
   NOT the reason it is safe to publish.** Brainstem Navigator forbids distributing anything derived from it
   outside your organisation; PAM50 states no licence at all; Diedrichsen is CC BY-ND, so distributing the
   meshes we make from it is forbidden outright. None of those three is about money. Harvard-Oxford is a
   separate case — FSL relicensed it to CC BY-SA 4.0 in August 2025 and it is held back pending a decision,
   not because it is non-commercial. **Never add a build mode that includes restricted data on the grounds
   that some particular use is non-commercial**, and never relax the gate on that reasoning. See
   [docs/editions.md](docs/editions.md#the-exclusion-is-unconditional).
6. **MNI coordinates and mesh ids are stable identifiers.** Content, tests, screenshots and saved links refer
   to them. Do not renumber, rename or re-register without being asked to.
7. **`NOTICE` is generated.** Never hand-edit it. It comes from `pipeline/config/sources.yaml` +
   `package.json` via `npm run notice`; `npm run notice -- --check` fails when it is stale.

## The two editions

A build is the **private** edition if and only if restricted data was built into it — it is decided by the
data, not by a flag. Four datasets are excluded — Brainstem Navigator and PAM50 because they may not be
redistributed, Diedrichsen because CC BY-ND forbids distributing the meshes we make from it, and
Harvard-Oxford as a hold pending review (see rule 5); they sit in `group: restricted` in `sources.yaml`, and
`atlas-download` refuses to fetch that group unless it is on the `private` branch or `ATLAS_ALLOW_RESTRICTED=1`.
The public edition substitutes openly licensed data for all four. Full detail, including how to obtain the
restricted ones, is in [docs/editions.md](docs/editions.md).

In `public/data/` the **plain names are always the public edition** (`manifest.json`, `content.json`,
`search-index.json`, `content.tr.json`); the private edition lives beside them as `*.private.json` and exists
only where restricted data was built. So a plain `npm run dev` or `npm run build` cannot leak.

| | |
|---|---|
| `npm run dev` / `npm run build` | public edition (`dist/`), gated |
| `npm run dev:private` / `npm run build:private` | full edition (`dist-private/`), ungated, do not publish |

## Checks

```bash
npm run check-tree                                # nothing private, restricted or generated is committed
npm run typecheck
npm test                                          # 47 unit tests
npm run content:validate                          # schemas, cross-links, word minimums, spelling, coverage
npm run citations:check
node scripts/check-data.ts --all                  # both manifests: meshes, volumes, coordinates
npm run notice -- --check
uv run --project pipeline atlas-qa                # the pipeline's own data gates
npx playwright install chromium && npm run e2e    # 24 browser tests
npm run build                                     # ends in the redistribution gate
python3 tools/i18n/prose.py check                 # Turkish overlays against the English entries
```

`.github/workflows/checks.yml` runs everything that works without generated data. The rest is a local job
before a release. Run the whole list before anything is published.

## Gotchas worth knowing before you spend an hour

- **Editing an English content entry invalidates its Turkish overlay.** Each `content/i18n/tr/<kind>/<id>.json`
  pins a sha1 of the English strings it was translated from, so a content-only change can fail
  `tools/i18n/prose.py check` and nothing else. Re-translate the overlay and re-pin; do not just bump the hash.
- **The content build validates against the *union* of both manifests.** An entry is not wrong because one
  edition drops its mesh — the editions ship different cortices. A structure whose meshes are all gone keeps
  its text with `meshIds: []`, and an `MniRef` keeps its coordinate and loses the mesh id.
- **`manifest.exclusions.json` missing is not an error.** It records what *this machine* dropped, so it only
  exists where the pipeline ran. Its absence means `public/data/` came from `npm run data`, in which case the
  data arrived already filtered and `check-public` runs in a reduced mode and says so. It stays a hard failure
  on a machine that has built restricted data.
- **The dev server used to disguise missing data.** Vite answers unknown paths with `index.html`, so
  `data/manifest.json` returned 200 with HTML and the app died in `JSON.parse`. The `dataPresence()` plugin in
  `vite.config.ts` now makes a missing `/data/*` file 404 honestly. If you touch that plugin, keep it
  registered *before* `privateEdition()`, which rewrites the same URLs.
- **Never package a `dist/` the gate has not just certified.** Use `scripts/release-data.sh`, which wipes
  `dist/`, builds, gates, and diffs the archive against the result. A stale `dist/` once put a forbidden
  licence file into a published archive.
- **Archives built on macOS need `COPYFILE_DISABLE=1`.** Otherwise BSD tar adds a `._<name>` AppleDouble twin
  per entry. macOS hides them from both listing and extraction, so they are invisible where they are created,
  and then appear on Linux as hundreds of files no manifest references. `release-data.sh` handles this and
  verifies with Python's `tarfile`, which does not share tar's blind spot.
- **`export: false` in `bp3d_selection.yaml` means registration input, not atlas mesh.** The seven gross-brain
  BodyParts3D concepts (brain, hemispheres, brainstem, cerebellum, lateral ventricles) are selected so that
  `atlas-register` can fit the frame on them, and `atlas-bp3d-meshes` retires anything they once left in
  `public/data/`. Do not ship them: they are a second specimen, 10–25 mm off the MNI-native meshes of the same
  structures, and they read as two brainstems and two cortices.
- **A structure that looks hollow or eroded is first an inside-out mesh.** The viewer culls back faces, so an
  inverted mesh shows its far wall through the missing near one. trimesh's `fix_normals()` does nothing to a
  mesh that is not watertight; `meshing.orient_outward` (inside `export_glb`) does, and `atlas-qa` fails any
  record with `insideOutShells` > 0. Check the sign of the volume before blaming the label or the triangle
  budget — both were blamed here first, wrongly. (Separately, cortical parcels are perforated by sulci in the
  label itself, and `AtlasSpec.fill_radius` closes that before meshing.)
- **One e2e test is timing-sensitive.** `interaction budget` measures frame pacing and can fail on a loaded
  machine. Re-run it alone before believing it.
- **`npm run e2e` needs a dev server with data**, except `e2e/no-data.spec.ts`, which fakes the missing
  manifest and is the one browser test CI can run.

## Adding or changing a data source

Everything flows from `pipeline/config/sources.yaml` — the licence records and the `sources` list. Add or
change an entry there, then:

```bash
uv run --project pipeline atlas-download --with <group>   # also rewrites public/data/licenses/<id>.txt
uv run --project pipeline atlas-manifest                  # licence + source records into both manifests
npm run notice                                            # regenerate NOTICE
npm run build                                             # and let check-public see it
```

Licence texts are the header (name, url, attribution) plus the verbatim legal code from
`pipeline/config/license_texts/<id>.txt` when one exists. **Do not file a dataset under another dataset's
licence because they arrive from the same place** — that is a real mistake this repository has already made
and corrected. Check for a per-file sidecar or a deposit record upstream, and if nobody states a licence, say
so in the licence name rather than guessing.

## Releasing

The data ships as a release asset, not in the repository:

```bash
npm version 1.0.2 --no-git-tag-version         # new tag = new asset name; never re-use one
scripts/release-data.sh v1.0.2                  # build, gate, verify, pack atlas-data-v1.0.2.tar.gz, re-pin
gh release create v1.0.2 --target origin/main --title ... --notes-file ...   # the release, from what origin has
gh release upload v1.0.2 atlas-data-v1.0.2.tar.gz                            # the asset, BEFORE the pin is pushed
git commit ... && git push                      # the pin lands, Pages fetches an asset that already exists
```

It builds fresh, gates, refuses anything that is not the public edition, verifies the archive and rewrites
the tag, asset name and SHA-256 pinned in `scripts/fetch-data.ts` so the fetcher and the asset cannot drift.
The Pages demo (`.github/workflows/pages.yml`) then fetches that same asset — data never reaches the deploy
from the repository.

**The asset goes up before the pin is pushed, and an asset is never replaced.** Origin pins a checksum, and
the push that changes it triggers a deploy that fetches the asset immediately; while v1.0.0 kept one asset
name and clobbered it in place, every re-pin failed that deploy once and needed a re-run, three times over.
A new version means a new asset name, so the asset can exist before anything points at it and nothing that
already points at the old one ever breaks. `release-data.sh --upload` refuses to overwrite an existing asset.

## Conventions

- Match the surrounding code: plain DOM and small modules in `src/`, no framework, no new dependency without a
  reason. Comments explain *why*, and the existing density is the target.
- British spelling in prose about the project; **American spelling in the clinical content** (`content:validate`
  enforces it there).
- Content is data. Never edit `content/` to make a build pass.
- Commit per logical stage, with a message that says what changed and why. Add:

  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  ```

- Do not push without being asked. Print the push commands instead.

## Not for clinical use

The atlas is an educational reference built on group-average templates, and its clinical text is a teaching
summary. Nothing in it is medical advice. Keep that framing intact in anything you write, and treat clinically
wrong content as a serious bug. The Turkish prose is machine-assisted and has not yet been reviewed by a
neurologist — say so where it matters rather than quietly implying otherwise.
