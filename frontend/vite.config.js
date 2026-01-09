import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173
    // proxy 설정 제거됨 - API Gateway(localhost:9000)를 통해 직접 연결
  }
})

