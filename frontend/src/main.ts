import { createApp } from 'vue'
import { createPinia } from 'pinia'

import './assets/main.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)

if (import.meta.env.DEV) {
  ;(window as any).__pinia = pinia
}

app.mount('#app')
