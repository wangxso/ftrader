import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        // target: 'http://10.0.0.172:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        // target: 'ws://10.0.0.172:8000',
        ws: true,
        changeOrigin: true,
        secure: false,
        configure: (proxy, _options) => {
          proxy.on('error', (err, _req, _res) => {
            // EPIPE 和 ECONNRESET 错误通常发生在连接正常关闭时，可以忽略
            if (err.code !== 'EPIPE' && err.code !== 'ECONNRESET') {
              console.error('WebSocket proxy error:', err)
            }
          })
        },
      },
    },
  },
})
