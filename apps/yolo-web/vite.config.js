import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:7860'

export default defineConfig({
  base: process.env.VITE_PUBLIC_BASE || '/',
  plugins: [vue()],
  server: {
    proxy: {
      '/api': apiTarget,
      '/outputs': apiTarget,
      '/reports': apiTarget,
    },
  },
})
