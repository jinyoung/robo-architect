import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './styles/main.css'
import { initializeAppSettings } from './config/appSettings'

// API Gateway 설정
const API_GATEWAY_URL = import.meta.env.VITE_API_GATEWAY_URL ?? 'http://localhost:9000'
const ARCHITECT_API_BASE = `${API_GATEWAY_URL}/architect`

// 원본 fetch 저장
const originalFetch = window.fetch.bind(window)

// fetch 래핑: 상대 경로 /api/* 를 게이트웨이 URL로 자동 변환
window.fetch = (input, init) => {
  if (typeof input === 'string' && input.startsWith('/api')) {
    // /api/xxx → http://localhost:9000/architect/api/xxx
    input = `${ARCHITECT_API_BASE}${input}`
  }
  return originalFetch(input, init)
}

// 전역 API URL 노출 (필요시 사용)
window.API_GATEWAY_URL = API_GATEWAY_URL
window.ARCHITECT_API_BASE = ARCHITECT_API_BASE

// 앱 설정 초기화 (document.title 등)
initializeAppSettings()

const app = createApp(App)
app.use(createPinia())
app.mount('#app')

