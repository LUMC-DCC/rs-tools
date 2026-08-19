import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    // Never inline a font. Vite turns assets under its size threshold into
    // `data:` URIs, which quietly puts two of the smaller subsets beyond
    // `font-src 'self'` and leaves those scripts rendering in a fallback face.
    // Emitting every font as a file keeps the policy at this origin alone.
    assetsInlineLimit: (filePath) => (/\.woff2?$/i.test(filePath) ? false : undefined),
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
