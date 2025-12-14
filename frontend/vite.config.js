import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Vite dev server config with proxy for /api to the backend container
export default defineConfig({
    plugins: [vue()],
    server: {
        host: true,
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://backend:8000',
                // target: 'http://localhost:8000',
                changeOrigin: true,
                secure: false,
                rewrite: (path) => path,
            },
        },
    },
})
