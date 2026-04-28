import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // HTTP API calls: /api/... → http://localhost:8000/...
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
        configure: (proxy) => {
          // Suppress EPIPE noise when backend isn't ready yet on startup
          proxy.on('error', () => {})
        }
      },
      // WebSocket events: /ws/... → ws://localhost:8000/ws/...
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true,
        configure: (proxy) => {
          // Suppress EPIPE noise — Vite tests the WS proxy on startup before
          // the backend is ready. This is harmless; the browser reconnects fine.
          proxy.on('error', () => {})
        }
      },
      // Static PDFs: /tailored/... → http://localhost:8000/tailored/...
      '/tailored': {
        target: 'http://localhost:8000',
        configure: (proxy) => {
          proxy.on('error', () => {})
        }
      }
    }
  }
})
