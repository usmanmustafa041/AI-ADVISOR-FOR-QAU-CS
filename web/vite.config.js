import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development the API runs on :8000; in production FastAPI serves this build itself.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  test: { environment: 'jsdom', globals: true },
})
