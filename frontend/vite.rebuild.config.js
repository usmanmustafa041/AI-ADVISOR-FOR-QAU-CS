import { defineConfig } from 'vite'
import base from './vite.config.js'

export default defineConfig({
  ...base,
  define: { 'import.meta.env.VITE_CHATBOT_REBUILD': JSON.stringify('true') },
  server: {
    ...base.server, host: '127.0.0.1', port: 5180, strictPort: true,
    proxy: {
      '/api/v3': { target: 'http://127.0.0.1:8010', changeOrigin: true },
      ...base.server.proxy,
    },
  },
})
