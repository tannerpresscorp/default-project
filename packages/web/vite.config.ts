import { defineConfig } from 'vite';

// In dev, /api/* is proxied to the Django server so the browser only talks to
// the Vite origin (no CORS setup needed). The api-client is used with an
// empty base URL, so requests resolve to the same origin.
export default defineConfig({
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});