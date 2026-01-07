import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './styles/main.css'
import { initializeAppSettings } from './config/appSettings'

// 앱 설정 초기화 (document.title 등)
initializeAppSettings()

const app = createApp(App)
app.use(createPinia())
app.mount('#app')

