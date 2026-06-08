import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'
import { readFileSync, existsSync } from 'fs'

function devTokenPlugin() {
  return {
    name: 'dev-token-inject',
    transformIndexHtml(html: string) {
      const tokenPath = resolve(__dirname, '../.boss_profile/.api_token')
      if (existsSync(tokenPath)) {
        const token = readFileSync(tokenPath, 'utf-8').trim()
        return html.replace('</head>', `<script>window.__API_TOKEN__='${token}';</script></head>`)
      }
      return html
    },
  }
}

export default defineConfig({
  plugins: [vue(), tailwindcss(), devTokenPlugin()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
      },
    },
  },
})
