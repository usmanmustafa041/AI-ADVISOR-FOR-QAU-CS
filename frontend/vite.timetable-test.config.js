import { defineConfig } from 'vite'
import rebuild from './vite.rebuild.config.js'

export default defineConfig({
  ...rebuild,
  server: {
    ...rebuild.server,
    port: 5182,
    proxy: { ...rebuild.server.proxy, '/api/v3': { target: 'http://127.0.0.1:8012', changeOrigin: true } },
  },
})
