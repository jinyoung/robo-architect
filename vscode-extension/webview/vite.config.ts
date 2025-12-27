import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      output: {
        // Use consistent file names (no hashing) for VS Code webview
        entryFileNames: 'assets/index.js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]'
      }
    },
    // Inline assets smaller than 4kb
    assetsInlineLimit: 4096
  },
  // Base path for VS Code webview (empty to use relative paths)
  base: '',
  server: {
    port: 5173,
    // Proxy for development (won't be used in VS Code)
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },
  define: {
    // Make sure we can detect VS Code environment
    '__IS_VSCODE_BUILD__': JSON.stringify(true)
  }
})

