import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only (npm run dev / start.bat): the app's own fetch calls are
    // relative (see src/services/api.ts), so this makes them reach the
    // FastAPI backend on :8000 without needing VITE_API_BASE_URL set. The
    // production build (start-prod.bat) doesn't go through Vite at all —
    // FastAPI serves it directly, same-origin, so this block never applies
    // there.
    proxy: {
      '/api': 'http://localhost:8001',
    },
  },
})
