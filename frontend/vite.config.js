import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
      'styles': resolve(__dirname, 'src/assets/styles'),
      'components': resolve(__dirname, 'src/components'),
      'pages': resolve(__dirname, 'src/pages'),
      'utils': resolve(__dirname, 'src/util'),
      'assets': resolve(__dirname, 'src/assets')
    },
    extensions: ['.js', '.json', '.jsx', '.mjs', '.ts', '.tsx', '.vue']
  },
  server: {
    port: 8888,
    host: '0.0.0.0',
    open: true,
    proxy: {
      '/api/ai_testcase/generate-stream': {
        target: 'http://127.0.0.1:8009',
        changeOrigin: true,
        // SSE 流式响应：禁用代理缓冲
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers['content-type']?.includes('text/event-stream')) {
              proxyRes.headers['Cache-Control'] = 'no-cache'
              proxyRes.headers['X-Accel-Buffering'] = 'no'
            }
          })
        }
      },
      '/api': {
        target: 'http://127.0.0.1:8009',
        changeOrigin: true,
        rewrite: (path) => path
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    sourcemap: false,
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          'element-plus': ['element-plus'],
          'monaco-editor': ['monaco-editor'],
          'echarts': ['echarts'],
          'vue-vendor': ['vue', 'vue-router', 'vuex'],
        }
      }
    }
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: `@use "sass:math";`
      }
    }
  },
  optimizeDeps: {
    include: ['vue', 'vue-router', 'vuex', 'axios', 'element-plus']
  }
})
