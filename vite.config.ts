import { defineConfig, type Plugin } from 'vite';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

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

export default defineConfig({
  base: './',
  server: { fs: { strict: true } },
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
  assetsInclude: ['**/*.glb'],
  plugins: process.env['ATLAS_EDITION'] === 'private' ? [privateEdition()] : [],
});
