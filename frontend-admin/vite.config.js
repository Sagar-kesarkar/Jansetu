import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Port 5174 so this can run alongside the citizen app on 5173. The demo shows
// both at once — a report filed on one screen appearing in the other's queue is
// the whole point of having two front ends, and it cannot be shown if starting
// the second one stops the first.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
  build: { outDir: 'dist', sourcemap: false },
})
