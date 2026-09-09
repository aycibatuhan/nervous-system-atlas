// `npm run data`: fetch the prebuilt PUBLIC atlas data into public/data/, so a fresh clone can run the app
// without building anything.
//   node scripts/fetch-data.ts [--force] [--keep-archive] [--from <file-or-url>]
//
// The data is not in the repository -- 63 MB of meshes, MRI volumes and label tables -- so it ships as a
// release asset instead. What this downloads is exactly the `dist/data` of `npm run build`: the edition that
// check-public has certified, 592 meshes with every restricted atlas already removed. There is no private
// bundle to fetch; that edition never leaves the machine that built it.
//
// The archive's SHA-256 is pinned below rather than trusted from the server, so a corrupted or substituted
// download fails loudly instead of producing a half-broken atlas.
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { createWriteStream, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync } from 'node:fs';
import { Readable } from 'node:stream';
import { pipeline } from 'node:stream/promises';
import { join, resolve } from 'node:path';

const RELEASE = {
  repo: 'aycibatuhan/nervous-system-atlas',
  tag: 'v1.0.0',
  asset: 'atlas-data-v1.0.0.tar.gz',
  sha256: 'aa09a6ec2f29e21892dd19329d15a834d6eea422683f7dbe4dd5c7a81e61e99a',
  bytes: 49186562,
};

const ROOT = resolve(import.meta.dirname, '..');
const DEST = join(ROOT, 'public/data');
const args = process.argv.slice(2);
const has = (f: string): boolean => args.includes(f);
const argOf = (f: string): string | undefined => (args.includes(f) ? args[args.indexOf(f) + 1] : undefined);
const url = argOf('--from') ?? `https://github.com/${RELEASE.repo}/releases/download/${RELEASE.tag}/${RELEASE.asset}`;
const mb = (n: number): string => `${(n / 1e6).toFixed(1)} MB`;

if (existsSync(join(DEST, 'manifest.json')) && !has('--force')) {
  console.error(`public/data/manifest.json already exists — this machine has atlas data.\n` +
    `Pass --force to replace it with the ${RELEASE.tag} bundle, or delete public/data/ first.`);
  process.exit(1);
}

const archive = join(ROOT, RELEASE.asset);

// ---- 1. fetch (unless a local file was handed to us)
const local = argOf('--from');
if (local && existsSync(local)) {
  console.log(`using ${local}`);
} else {
  console.log(`downloading ${url}`);
  const res = await fetch(url, { redirect: 'follow' });
  if (!res.ok || !res.body) {
    console.error(`\ndownload failed: ${res.status} ${res.statusText}\n` +
      `If the release has not been published yet, build the data instead — see docs/pipeline.md.`);
    process.exit(1);
  }
  const total = Number(res.headers.get('content-length') ?? 0);
  let seen = 0, lastPct = -1;
  const body = Readable.fromWeb(res.body as Parameters<typeof Readable.fromWeb>[0]);
  body.on('data', (c: Buffer) => {
    seen += c.length;
    const pct = total ? Math.floor((seen / total) * 100) : -1;
    if (pct !== lastPct && pct % 5 === 0) { lastPct = pct; process.stdout.write(`\r  ${pct}%  ${mb(seen)}`); }
  });
  await pipeline(body, createWriteStream(archive));
  process.stdout.write(`\r  done, ${mb(statSync(archive).size)}\n`);
}
const file = local && existsSync(local) ? local : archive;

// ---- 2. verify before unpacking anything
const digest = createHash('sha256').update(readFileSync(file)).digest('hex');
if (RELEASE.sha256.startsWith('__')) {
  console.log(`sha256 ${digest}  (no checksum pinned in this checkout — not verified)`);
} else if (digest !== RELEASE.sha256) {
  console.error(`\nchecksum mismatch — refusing to unpack.\n  expected ${RELEASE.sha256}\n  got      ${digest}\n` +
    `Delete ${RELEASE.asset} and try again; if it keeps failing, the release asset may have been replaced.`);
  process.exit(1);
} else {
  console.log(`sha256 ok (${digest.slice(0, 16)}…)`);
}

// ---- 3. unpack into public/data/
mkdirSync(DEST, { recursive: true });
console.log(`unpacking into public/data/`);
execFileSync('tar', ['-xzf', file, '-C', DEST], { stdio: 'inherit' });
if (!local && !has('--keep-archive')) rmSync(archive, { force: true });

// An archive packed on macOS without COPYFILE_DISABLE=1 carries a ._<name> AppleDouble twin for every entry.
// macOS tar hides them on both listing and extraction, so they are invisible where such an archive is made and
// only appear here, on Linux -- as files no manifest references, which is exactly what check-public rejects.
const appleDouble = (dir: string, out: string[] = []): string[] => {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) appleDouble(p, out);
    else if (name.startsWith('._')) out.push(p);
  }
  return out;
};
const junk = appleDouble(DEST);
if (junk.length) {
  console.warn(`\nremoved ${junk.length} AppleDouble (._*) file(s) the archive should not have contained.`);
  console.warn('The release asset was packed without COPYFILE_DISABLE=1; please report it.');
  for (const f of junk) rmSync(f, { force: true });
}

// ---- 4. say what arrived
const manifest = JSON.parse(readFileSync(join(DEST, 'manifest.json'), 'utf8')) as {
  meshes: unknown[]; volumes: Record<string, unknown>; edition?: string;
};
console.log(`\npublic/data/: ${manifest.meshes.length} meshes, ${Object.keys(manifest.volumes).length} volumes, ` +
  `edition "${manifest.edition ?? 'public'}"`);
console.log('run `npm run dev` and open http://localhost:5173');
