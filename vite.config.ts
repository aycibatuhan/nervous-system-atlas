import { defineConfig, type Plugin } from 'vite';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

// The About panel names the version a build came from, so a bug report can say which one it is.
const version = (JSON.parse(readFileSync(resolve(import.meta.dirname, 'package.json'), 'utf8')) as { version: string }).version;

// The app always fetches data/manifest.json, data/content.json, data/search-index.json and data/content.tr.json.
// In public/data/ those plain names are the PUBLIC edition, which is what `npm run dev` should serve — the
// private edition is opt-in. ATLAS_EDITION=private points the same four requests at the .private.json bundles,
// which only exist on a machine that has built the restricted data.
const PRIVATE_BUNDLES: Record<string, string> = {
  '/data/manifest.json': 'manifest.private.json',
  '/data/content.json': 'content.private.json',
  '/data/search-index.json': 'search-index.private.json',
  '/data/content.tr.json': 'content.tr.private.json',
};

function privateEdition(): Plugin {
  const dir = resolve(import.meta.dirname, 'public/data');
  return {
    name: 'atlas-private-edition',
    apply: 'serve',
    configureServer(server) {
      const missing = Object.values(PRIVATE_BUNDLES).filter((f) => !existsSync(resolve(dir, f)));
      if (missing.length) {
        server.config.logger.warn(`ATLAS_EDITION=private: ${missing.join(', ')} not built — serving the public edition`);
        return;
      }
      server.config.logger.info('ATLAS_EDITION=private: serving the private edition (do not publish what you see)');
      server.middlewares.use((req, _res, next) => {
        const path = (req.url ?? '').split('?')[0] ?? '';
        const swap = PRIVATE_BUNDLES[path];
        if (swap) req.url = (req.url ?? '').replace(path, `/data/${swap}`);
        next();
      });
    },
  };
}

// A fresh clone has no public/data/ at all: the pipeline builds it, or `npm run data` fetches it. Two things
// go wrong without this plugin. The dev server answers every unknown path with index.html, so `data/manifest.json`
// comes back 200 with a page of HTML and the app dies on `JSON.parse` with "Unexpected token '<'"; and nothing in
// the terminal ever mentions the missing data. So: say it once at startup, and let a missing data file 404 like
// it would on a real server, which is also what the app's own check expects.
function dataPresence(): Plugin {
  const dir = resolve(import.meta.dirname, 'public/data');
  return {
    name: 'atlas-data-presence',
    apply: 'serve',
    configureServer(server) {
      if (!existsSync(resolve(dir, 'manifest.json'))) {
        const l = server.config.logger;
        l.warn('');
        l.warn('  no atlas data: public/data/manifest.json is missing, so the app will show a setup message.');
        l.warn('  `npm run data` downloads the prebuilt public bundle (~50 MB) from the v1.0.0 release,');
        l.warn('  or build it yourself from the source atlases -- see docs/pipeline.md.');
        l.warn('');
      }
      server.middlewares.use((req, res, next) => {
        const path = (req.url ?? '').split('?')[0] ?? '';
        if (!path.startsWith('/data/') || existsSync(resolve(dir, decodeURIComponent(path.slice('/data/'.length))))) return next();
        res.statusCode = 404;
        res.setHeader('content-type', 'text/plain');
        res.end(`${path} is not built -- run \`npm run data\`, or see docs/pipeline.md`);
      });
    },
  };
}

export default defineConfig({
  base: './',
  server: { fs: { strict: true } },
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
  define: { __APP_VERSION__: JSON.stringify(version) },
  assetsInclude: ['**/*.glb'],
  plugins: [dataPresence(), ...(process.env['ATLAS_EDITION'] === 'private' ? [privateEdition()] : [])],
});
