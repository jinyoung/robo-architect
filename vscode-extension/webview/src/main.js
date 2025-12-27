import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import { isVSCode, notifyReady, onMessage } from './utils/vscode'

import '@vue-flow/core/dist/style.css'
import '@vue-flow/core/dist/theme-default.css'
import './styles/main.css'

const app = createApp(App)
app.use(createPinia())

// Make VS Code utilities available globally
app.config.globalProperties.$isVSCode = isVSCode
app.config.globalProperties.$notifyReady = notifyReady
app.config.globalProperties.$onMessage = onMessage

app.mount('#app')

// Notify VS Code that the webview is ready
if (isVSCode()) {
  notifyReady()
}

