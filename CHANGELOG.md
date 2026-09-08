# Changelog

All notable changes to this project are recorded in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

One version number covers the whole atlas, because the three halves of it are only
meaningful together: the browser application in `src/`, the Python data pipeline in
`pipeline/` that builds the meshes, volumes, label maps and manifest, and the authored
content in `content/` with its bibliography and its Turkish overlays. The app reads a
manifest and a content bundle that the pipeline and the content build produced from the
same tree, so a change to any one of the three can move the version.

<!--
No remote is configured yet, so there are no release or compare links at the bottom of
this file. When the repository is published, add link definitions of the form
[1.0.0]: https://<host>/<owner>/nervous-system-atlas/releases/tag/v1.0.0
and replace the placeholder host with the real one.
-->

## [1.0.0] - 2026-09-08

First public release. There is no earlier published version, so this section describes
what the project is rather than what changed since last time; the pre-release work that
produced it is summarised under [Development history](#development-history).

### Added

**The atlas.** A local, browser-based 3D atlas of clinical neuroanatomy with synchronised
MRI slices, arterial territory maps, pathway tracing, a syndrome and lesion mode, clinical
topics, a glossary and a quiz. Everything is expressed in one coordinate frame,
MNI152NLin2009cAsym RAS millimetres, so the meshes, the T1/T2 slices and the label
overlays line up exactly. The atlas is an educational reference and carries a
not-for-clinical-use disclaimer in the README and in the About panel.

**Application.** Vite, TypeScript and three.js. A tri-state structure tree with group solo
and defaults, a toolbar search over structures, pathways and syndromes, orbit/pan/zoom with
frame-rate-independent damping and touch support, click and double-click selection against
both the meshes and the MRI slice, and a content panel with tabs for overview, anatomy,
connections, function, blood supply, imaging, clinical, pitfalls and sources. Hash routes
address structures, pathways, syndromes, topics, the glossary and the quiz, so any view can
be linked to. Physically based materials over an anatomical palette, with a Quality toggle
that adds ambient occlusion, a soft key-light shadow and anti-aliasing; high-detail meshes
load lazily behind small stand-ins. Axial, coronal and sagittal slices with T1/T2, peel
mode, territory tint, label outlines and a cord MRI that switches itself on below the
foramen magnum.

**Data pipeline.** A `uv`-managed Python package (`atlas-download`, `atlas-volumes`,
`atlas-bp3d-select`, `atlas-register`, `atlas-bp3d-meshes`, `atlas-atlas-meshes`,
`atlas-venat`, `atlas-lc-metamask`, `atlas-aan`, `atlas-derived`, `atlas-labels`,
`atlas-pam50`, `atlas-spine-generic`, `atlas-fudan-spine`, `atlas-cord-public`,
`atlas-manifest`, `atlas-qa`) that downloads and digest-pins its sources, resamples volumes
onto the MNI grid, meshes label masks through a signed-distance path with Taubin smoothing,
per-class triangle budgets and cross-parcel welding, landmark-registers the BodyParts3D and
Z-Anatomy specimens into MNI, constructs the meshes no source ships, and writes the
manifest the app reads. Generated data under `public/data/` is not committed.

**Two editions.** The private edition is 662 meshes and is everything the pipeline can
build; it stays local, because Harvard-Oxford, the Diedrichsen cerebellar atlas, the
Brainstem Navigator 7 T nuclei and the PAM50 cord template may not be redistributed. The
public edition is 592 meshes and is what may be shared, under Apache 2.0 for the code and
CC BY-SA 4.0 for the data and content. In it those four are replaced by CerebrA/DKT
cortical parcels, a FastSurfer CerebNet cerebellum, landmark-anchored brainstem markers, an
openly licensed locus coeruleus meta-mask, and a cord MRI composed here from spine-generic
and Fudan whole-spine data. A dataset leaves the public edition when its licence record is
flagged non-commercial or no-redistribution, and nothing else is special-cased. The public
edition is what `npm run build` produces and what `check-public` gates, so the default build
is the checked one; the full edition is `npm run build:private` and never leaves the machine.

**Content.** 825 authored entries: 379 structures, 12 cranial nerves, 25 pathways, 125
syndromes, 19 topics, 205 glossary terms and 60 quiz vignettes. All prose is original,
validated against zod schemas, and checked for cross-links, word minimums, spelling and
overlap against a private reference corpus. Every mesh in the manifest has an entry.

**Citations.** 2387 citations to 657 open-access sources — StatPearls chapters on the NCBI
Bookshelf, open-access articles in PubMed Central, and openly licensed reference pages — so
every claim can be read and checked without a paywall. No printed textbook is cited
anywhere in the shipped atlas. Bibliography entries are only ever marked verified by a tool
reading live source metadata, and the citation check fails on a malformed citation, an
unknown reference, an unverified entry or an entry nothing cites.

**Turkish edition.** A TR/EN switch kept in the URL hash and in `localStorage`, 289
interface strings typed against the English table, FIPAT TA2/TNA Latin terms applied to 227
entries with Turkish search synonyms, and the clinical prose of all 825 entries translated
as overlays under `content/i18n/tr/`, pinned to the hash of their English source. The
Turkish prose is machine-assisted and is awaiting review by a Turkish neurologist; the
interface says so.

**Licensing and provenance.** Apache 2.0 for the code, CC BY-SA 4.0 for the data and the
content, a `NOTICE` generated from `pipeline/config/sources.yaml` so every source's licence
travels with the build, and an About and credits panel that shows the same records in the
app.

**Checks.** TypeScript typecheck, Vitest unit tests, Playwright end-to-end smoke tests,
`check-data` over the generated data, `check-public` over the public build, the content
build's own validation and the pipeline's `atlas-qa` gates.

### Fixed

Late fixes made while preparing this release:

- `characteriztic` misspelling corrected in three syndromes and two topics.
- Wallenberg syndrome: the palate and uvula deficit wording corrected against the cited
  sources.
- Connection `from` and `to` values are rendered as entry names instead of raw ids.
- The toolbar search box no longer collapses at narrow window widths.
- Turkish mode carries a visible notice that the clinical prose is machine-assisted and
  under review.

## Development history

47 commits between 2026-09-05 and 2026-09-07, before any version was published. They are
grouped by theme below rather than listed in order; short hashes are given so the actual
commits can be found.

### Bootstrap, data pipeline and registration (2026-09-05 – 2026-09-06)

- `59de8dc` Bootstrapped the atlas: the corpus tools, the MNI mesh and volume pipeline
  (`download`, `volumes`, `meshing`, `atlas_meshes`, `labels`, `manifest`, `spaces`, the
  source catalogue and its lock file) and a first three.js viewer.
- `e7b73d6` Added the content schema, the content build, the hash router and the content
  panel, together with the first content batch (arteries and territories, 32 entries) and
  the BodyParts3D structure selection.
- `75ae25d` Landmark-affine registration of BodyParts3D into MNI, with 54 registered meshes
  — vessels, the optic pathway, orbital nerves, cord and meninges — alongside content
  batches 2 and 3.
- `92fae4d` Split and corrected the vertebral arteries, anchored the Z-Anatomy midbrain,
  and put spinal-level labels into the interface.

### Mesh building (2026-09-05 – 2026-09-06)

- `3f7710a` Z-Anatomy export from Blender (`bpy`) plus its landmark registration, adding 117
  nerve, sinus and nucleus meshes for 540 in total.
- `aa02fef` Filled in the missing meshes and scaffolded the Brainstem Navigator ingest.
- `ede5bee` Brought in the Brainstem Navigator 7 T nuclei and corrected the sub-cranial
  registration, alongside the first cord MRI (below).

### Content authoring (2026-09-05 – 2026-09-06)

Written in numbered batches with the Python authoring helpers in `tools/author/`.

- `ee10b7a`, `f3662ab`, `a30e422`, `82a917d`, `36f6431` Batches 4 to 12: cerebellum,
  ventricles and CSF, diencephalon, the cortical lobes, limbic and white matter, basal
  ganglia, spinal cord, meninges, venous sinuses, peripheral nerves, plexuses, the
  neuromuscular junction, autonomics and ganglia, then cranial nerves I–XII — 198 entries by
  the end of it.
- `5d2e88c` Batch 13: 25 pathways and the pathway panel route.
- `3eb05e4`, `1313e7b` Batch 14: 103 syndromes across vascular, lacunar, cortical,
  brainstem, cerebellar and cranial nerve territory.
- `df37cfa` Batches 15 and 16: extended structures and syndromes (356 of 359).
- `03c6245` The first glossary (67 terms) and quiz deck (30 vignettes) with their panels and
  routes.
- `f6cfcc4`, `624c702` The topic kind end to end (schema, build, panel, router) with 92 new
  structure entries for cortical, limbic, diencephalic, brainstem, pallidal and cerebellar
  meshes, then entries for every remaining tract, arterial territory and reference mesh,
  reaching zero manifest structures without content.
- `0ef4802` 19 clinical topics and 18 further Z-Anatomy meshes (cutaneous and plexus nerves,
  spinal grey and white matter) with their entries; the plagiarism check at zero hits.
- `149c6a2` 138 more glossary terms, 30 more quiz vignettes, a topic end-to-end test, a
  panel and selection fix, and the README counts.

### Citations migrated to open access (2026-09-06)

- `aa02fef` Migrated every citation in the atlas to open-access sources — StatPearls
  chapters and PubMed Central articles — with the citation tooling in `tools/cite/`
  (`catalog.py`, `migrate.py`, `statpearls.py`, `oa.py`) that harvests the chapter catalogue,
  scores candidates by a rarity-weighted title match, reads section names from the live
  chapter rather than guessing them, and records the decisions the automatic pass cannot
  make.

### Rendering and interaction (2026-09-05 – 2026-09-07)

- `2c5d577` Syndrome mode: the bar, the panel, the lesion marker, the deficit stepper, the
  mirror control and the toolbar search box.
- `b85ce48` Fixed the MNI reference resolver clobbering pathway waypoints, kept ids out of
  the spelling normaliser, and added the README and the bundle tests.
- `eed77a7` Leaving the quiz panel no longer clears the syndrome highlights.
- `a06d555` Added the `atlas-qa` gate step, an arterial source alias, and clearer involved
  and dimmed materials.
- `dcbf182`, `e6df5ee` Playwright smoke tests (load, tree select, syndrome route, quiz and
  glossary) and the ignore rules for their artefacts and the Blender venv.
- `3b861ea` The empty syndrome bar hides itself when no syndrome is active, via the `hidden`
  attribute rather than a display rule.
- `2c6bde2` Fixed pointer input: hidden overlays no longer cover the canvas. Richer orbit
  controls, double-click focus, a click threshold, and an end-to-end pointer test.
- `88853ce` Physically based rendering and higher-detail geometry, with the reference-shot
  and montage scripts used to compare before and after.
- `37626e5` The `p` shortcut peels at the slice last toggled with `a`, `c` or `s`, not only
  the axial one.
- `32c377b` Cast the citations against the typed entry in the panels.

### The spinal cord MRI (2026-09-06 – 2026-09-07)

- `ede5bee` The private edition's cord MRI: `atlas-pam50` curve-reformats the straightened
  PAM50 template onto the centreline of the atlas's own cord surface, with a spinal-level
  label volume on the same grid. Smoother interaction, group toggles and more specific
  references landed with it.
- `94cfc54` A first public-edition cord from the spine-generic multi-subject database,
  alongside the other public-edition mesh work below.
- `bf29aef` Registered the Fudan whole-spine dataset (CC BY 4.0) and added the
  `atlas-fudan-spine` and `atlas-cord-public` steps.
- `d5ec412` A whole-cord public MRI: the Fudan whole-spine T2 template composed with
  spine-generic by `atlas-cord-public`, so the public edition's slices now run the length of
  the cord and into the sac.

### The public edition and the redistribution gate (2026-09-06 – 2026-09-07)

- `2a5c2ae` Apache 2.0 for the code, CC BY-SA 4.0 for the data and the content, a generated
  `NOTICE`, and the About and credits panel.
- `b019be7` Split the build into public and private editions: a separate public build,
  `check-public`, the manifest's edition filter, and the tests and shots that guard them.
- `222aca8` CC0 CerebrA/DKT cortex and an `aseg` cerebellum for the public edition, plus the
  CC BY locus coeruleus meta-mask.
- `a6059eb` Landmark-anchored brainstem markers, the AAN atlas scaffold and the
  public-edition cord blocks.
- `48aa717` Imported the Harvard Ascending Arousal Network atlas ROIs into the public
  edition and wired them into the entries.
- `94cfc54` FastSurfer cerebellar lobules, open-sized markers for every brainstem nucleus,
  the vertebral filum and the spine-generic cord MRI.
- `7f94ad8` The not-for-clinical-use disclaimer in the README and the About panel, and the
  BodyParts3D licence record updated to CC BY 4.0 with the share-alike chain verified.

### Turkish edition (2026-09-07)

- `6f0b6aa` The terminology review table: `tools/i18n/terms.py` matches every structure,
  cranial nerve and pathway to FIPAT TA2 and TNA, Wikidata and Turkish Wikipedia.
- `0c937d2` Added a relation column to the review (exact, synonym, narrower, broader, fuzzy,
  related, none), related FIPAT terms for umbrella entries and subdivision notes between TA2
  and TNA; exact-name matches now outrank synonym clusters, so the lateral corticospinal
  tract resolves to TA2 6095 rather than the pyramidal tract.
- `051dc82` The apply step: FIPAT Latin terms (TNA first, TA2 as the fallback) and Turkish
  search synonyms written into 227 entries, `names.tr` and `synonymsByLang.tr` added to the
  schemas, search index and content types, and the four terminology sources registered in
  `sources.yaml` with their own section in `NOTICE`.
- `336466a` The Turkish interface: the locale switch (shortcut `L`) kept in the URL hash and
  `localStorage`, 289 interface strings in `src/i18n/{en,tr}.ts`, Latin structure names with
  the English name as a secondary line, an English tag on untranslated prose, a bilingual
  About panel, unit and end-to-end tests and `scripts/shots-tr.mjs`.
- `881efab` The Turkish prose pipeline: `content/i18n/tr/<kind>/<id>.json` overlays pinned to
  the hash of their English source, checked by `tools/i18n/prose.py` and applied by the
  content build into `content.tr.json`, which the app fetches the first time Turkish is
  selected; `STYLE-tr.md` for the translators.
- `4a26d9c` The Turkish clinical prose itself: 825 overlays across structures, cranial
  nerves, pathways, syndromes, topics, glossary and quiz, written against `STYLE-tr.md`,
  checked with no errors and terminology-normalised. `content.tr.json` ships in both
  editions and `check-public` treats it like the English bundle.
