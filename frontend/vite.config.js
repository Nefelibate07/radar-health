import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    // 端口被占用时直接报错,不自动换端口:
    // desktop:dev 的 wait-on tcp:5173 与 Electron 加载地址都写死 5173,
    // 静默漂移到 5174 会导致桌面端白屏、且看的是旧进程的页面。
    strictPort: true
  }
})
