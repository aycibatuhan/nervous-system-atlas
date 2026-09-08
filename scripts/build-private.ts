// `npm run build:private`: the FULL edition into dist-private/ — every mesh and volume this machine has built,
// including the ones whose licence is non-commercial or forbids passing derived files on.
//   node scripts/build-private.ts [--skip-manifest] [--skip-content] [--skip-vite]
//
// dist-private/ MUST NOT BE PUBLISHED. Nothing here is filtered and no gate runs over it; that is the whole
// difference from `npm run build`, which produces the redistributable dist/ and checks it.
//
// The app always fetches data/manifest.json, data/content.json and data/search-index.json, so the last step
// puts the private bundles under those names inside the build and removes the public ones. public/data/ itself
// is never touched.
import { execFileSync } from 'node:child_process';
import { existsSync, copyFileSync, rmSync, readFileSync } from 'node:fs';
import { resolve, join } from 'node:path';

const ROOT = resolve(import.meta.dirname, '..');
const SRC = join(ROOT, 'public/data');
const OUT = join(ROOT, 'dist-private');
const DATA = join(OUT, 'data');
const args = new Set(process.argv.slice(2));
const step = (s: string) => console.log(`\n── ${s}`);
const run = (cmd: string, argv: string[]) => execFileSync(cmd, argv, { cwd: ROOT, stdio: 'inherit', env: process.env });

if (!existsSync(join(SRC, 'manifest.private.json'))) {
  console.error('build:private: public/data/manifest.private.json is missing — this machine has not built any\n' +
    'restricted data, so there is no private edition. `atlas-download --with restricted` on the private branch\n' +
    '(plus the manual Brainstem Navigator step) is what creates one; `npm run build` is the edition you have.');
  process.exit(1);
}

// ---- 1. the manifests (writes both editions)
const venv = join(ROOT, 'pipeline/.venv/bin/atlas-manifest');
if (!args.has('--skip-manifest') && existsSync(venv)) { step('atlas-manifest'); run(venv, []); }

// ---- 2. the private content bundle
if (!args.has('--skip-content')) { step('content build --private'); run(process.execPath, ['scripts/content/build.ts', '--private']); }

// ---- 3. vite
if (!args.has('--skip-vite')) { step('vite build --outDir dist-private'); run(join(ROOT, 'node_modules/.bin/vite'), ['build', '--outDir', 'dist-private', '--emptyOutDir']); }

// ---- 4. the private bundles take the plain names the app asks for
step('swap in the private bundles');
for (const [from, to] of [['manifest.private.json', 'manifest.json'], ['content.private.json', 'content.json'],
  ['search-index.private.json', 'search-index.json'], ['content.tr.private.json', 'content.tr.json']] as const) {
  if (!existsSync(join(DATA, from))) { console.error(`build:private: ${from} is not in the build`); process.exit(1); }
  copyFileSync(join(DATA, from), join(DATA, to));
  rmSync(join(DATA, from));
}
rmSync(join(DATA, 'manifest.exclusions.json'), { force: true });
for (const f of ['LICENSE', 'NOTICE']) if (existsSync(join(ROOT, f))) copyFileSync(join(ROOT, f), join(OUT, f));

const man = JSON.parse(readFileSync(join(DATA, 'manifest.json'), 'utf8')) as { meshes: unknown[]; volumes: Record<string, unknown>; edition?: string };
console.log(`\ndist-private/: ${man.meshes.length} meshes, ${Object.keys(man.volumes).length} volumes, edition "${man.edition ?? 'private'}"`);
console.log('dist-private/ contains data that may not be redistributed. Do not publish it, do not deploy it,\n' +
  'and do not copy it anywhere that is shared. `npm run build` is the edition that may leave this machine.');
