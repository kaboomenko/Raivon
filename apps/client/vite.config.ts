import { defineConfig } from 'vite';
import { viteSingleFile } from 'vite-plugin-singlefile';

// Single-file build: one self-contained index.html that opens from any static host
// (or a claude.ai page) on iPhone Safari without extra files.
export default defineConfig({
  base: './',
  plugins: [viteSingleFile()],
  build: {
    target: 'es2022',
    assetsInlineLimit: 100_000_000,
    chunkSizeWarningLimit: 4000,
  },
});
