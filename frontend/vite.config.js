import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// /api      -> the portal backend (courses, fees, timetable, accounts ...)
// /advisor  -> the new chatbot engine (answers, sources, conversation history)
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/advisor': {
        target: process.env.VITE_ADVISOR_PROXY || 'http://127.0.0.1:8010',
        changeOrigin: true,
        xfwd: true, // pass the student's real IP so rate limits are per student, not per proxy
        rewrite: (path) => path.replace(/^\/advisor/, ''),
      },
      '/api': { target: process.env.VITE_API_PROXY || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
