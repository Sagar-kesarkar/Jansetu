import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Nothing exotic on purpose. The build has to succeed on Netlify's free tier
// from a cold clone, so no custom transforms and no native dependencies.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: { outDir: 'dist', sourcemap: false },
})
