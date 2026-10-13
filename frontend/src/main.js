import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './AppShell.vue'
import router from './router'
import './styles/base.css'
import './styles/industrial-shell.css'

createApp(App).use(ElementPlus).use(router).mount('#app')
