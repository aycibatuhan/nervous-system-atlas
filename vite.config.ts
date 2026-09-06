import { defineConfig } from 'vite';

export default defineConfig({
  base: './',
  server: { fs: { strict: true } },
  build: { target: 'es2022', chunkSizeWarningLimit: 1500 },
  assetsInclude: ['**/*.glb'],
});
