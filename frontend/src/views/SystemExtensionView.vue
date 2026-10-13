<template>
  <section class="demo-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">SYSTEM EXTENSION & INTEGRATION</span>
        <h1>系统扩展</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">数据源：合成演示快照</span>
        <button class="head-btn secondary" @click="goHome">返回主界面</button>
          <button class="head-btn" @click="showAdd = true">登记新模块</button>
      </div>
    </header>

    <div class="screen-grid">
      <article class="panel module-panel">
        <h2>已登记模块</h2>
        <p class="panel-note">本页管理模块登记与启用状态，不执行外部代码。</p>
        <div class="module-list">
          <section v-for="m in modules" :key="m.name" class="module-card">
            <div class="module-head">
              <div class="module-icon">{{ m.icon }}</div>
              <div class="module-title">
                <h3>{{ m.name }}</h3>
                <span :class="m.enabled ? 'accent-green' : 'accent-pink'">{{ m.enabled ? '已启用' : '已停用' }}</span>
              </div>
              <label class="switch">
                <input :checked="Boolean(m.enabled)" type="checkbox" @change="toggleModule(m)" />
                <span class="slider" />
              </label>
            </div>
            <p class="module-desc">{{ m.description }}</p>
            <div class="module-meta">
              <span>版本: {{ m.version }}</span>
              <span>接口: {{ m.api_path }}</span>
            </div>
          </section>
        </div>
      </article>

      <article class="panel data-panel">
        <h2>数据源连接</h2>
        <div class="conn-list">
          <div v-for="c in connectionsWithSim" :key="c.name" class="conn-row">
            <span>{{ c.name }}</span>
            <span :class="c.status === '已连接' ? 'accent-green' : 'accent-yellow'">{{ c.status }}</span>
            <span class="latency">{{ c.displayLatency }}</span>
          </div>
        </div>

        <h2 class="mt">扩展日志</h2>
        <div class="log-list">
          <div v-for="(log, idx) in logs" :key="idx" class="log-row">
            <span class="time">{{ log.time }}</span>
            <span>{{ log.message }}</span>
          </div>
        </div>
      </article>
    </div>

    <div v-if="showAdd" class="modal-overlay" @click.self="showAdd = false">
      <div class="modal">
        <h3>接入新模块</h3>
        <div class="form-row">
          <label>模块名称</label>
          <input v-model="newModule.name" type="text" placeholder="例如：气象数据接入" />
        </div>
        <div class="form-row">
          <label>接口地址</label>
          <input v-model="newModule.api" type="text" placeholder="例如：/api/health/evaluate" />
        </div>
        <div class="modal-actions">
          <button class="head-btn secondary" @click="showAdd = false">取消</button>
          <button class="head-btn" @click="addModule">确认接入</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import axios from 'axios'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { API_PREFIX } from '../config/backend'

const router = useRouter()
const showAdd = ref(false)

const modules = ref([])

const connections = ref([
  { name: '雷达数据采集器', status: '由协议回放提供', latency: '--' },
  { name: '后端算法服务', status: '由当前快照驱动', latency: '--' },
  { name: 'SQLite 快照库', status: '由场景引擎写入', latency: '--' }
])
const connectionsWithSim = computed(() => connections.value.map((c) => ({ ...c, displayLatency: c.latency })))

const logs = ref([
  { time: '10:24:36', message: '健康预测模型加载完成' },
  { time: '10:24:12', message: '关系图导入服务已就绪' },
  { time: '10:23:58', message: '健康数据库接口已就绪' }
])

const newModule = reactive({ name: '', api: '' })

// 统一用后端返回的完整记录回写原始列表，确保状态及规范化字段立即同步。
const replaceModule = (updatedModule) => {
  const index = modules.value.findIndex((item) => item.id === updatedModule?.id)
  if (index >= 0) modules.value[index] = updatedModule
}

const addModule = async () => {
  if (!newModule.name || !newModule.api) return
  try {
    const { data: body } = await axios.post(`${API_PREFIX}/extensions`, { name: newModule.name, api_path: newModule.api })
    modules.value.unshift(body.data)
    logs.value.unshift({
      time: new Date().toLocaleTimeString('zh-CN', { hour12: false }),
      message: `新模块 "${newModule.name}" 已登记`
    })
    newModule.name = ''
    newModule.api = ''
    showAdd.value = false
  } catch (error) { window.alert(error.response?.data?.error || error.message || '登记模块失败') }
}

const toggleModule = async (module) => {
  try {
    const { data: body } = await axios.put(`${API_PREFIX}/extensions/${module.id}`, { enabled: !Boolean(module.enabled) })
    replaceModule(body.data)
  } catch (error) { window.alert(error.response?.data?.error || error.message || '更新模块状态失败') }
}

const loadModules = async () => {
  try {
    const { data: body } = await axios.get(`${API_PREFIX}/extensions`)
    modules.value = body.data
  } catch (error) { window.alert(error.response?.data?.error || error.message || '读取模块列表失败') }
}

const goHome = () => router.push('/health')
onMounted(loadModules)

</script>

<style scoped>
.demo-screen {
  min-height: calc(100vh - 20px);
  padding: 12px;
  color: #d7f3ff;
  border: 2px solid #18bfff;
  border-radius: 12px;
  background:
    radial-gradient(circle at 20% 0%, rgba(66, 166, 255, 0.18), transparent 40%),
    linear-gradient(180deg, #05153d 0%, #07255f 48%, #06194b 100%);
  box-shadow: inset 0 0 35px rgba(23, 125, 220, 0.22), 0 0 16px rgba(24, 190, 255, 0.22);
}

.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
}

.title-block {
  display: grid;
  gap: 2px;
}

.eyebrow {
  margin: 0;
  color: #86dfff;
  font-size: 11px;
  letter-spacing: 1.5px;
}

h1 {
  margin: 0;
  font-size: 28px;
  color: #f2fbff;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.head-btn {
  height: 40px;
  padding: 0 16px;
  border-radius: 8px;
  border: 1px solid rgba(108, 216, 255, 0.36);
  background: linear-gradient(180deg, #1f5cad, #153f84);
  color: #e6fbff;
  cursor: pointer;
  transition: 0.2s ease;
}

.head-btn.secondary {
  background: linear-gradient(180deg, #19467f, #12345f);
}

.head-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 0 12px rgba(89, 205, 255, 0.28);
}

.sim-toggle {
  height: 40px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  background: linear-gradient(180deg, #19467f, #12345f);
  color: #c6ecff;
  font-size: 13px;
  cursor: pointer;
  transition: 0.2s ease;
}

.sim-toggle.active {
  background: linear-gradient(180deg, #1f5cad, #153f84);
  border-color: #5cd8ff;
  color: #e6fbff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.25);
}

.screen-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: 1.4fr 1fr;
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
  padding: 14px;
}

.module-panel h2,
.data-panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.module-list {
  display: grid;
  gap: 10px;
}

.module-card {
  border: 1px solid rgba(91, 195, 255, 0.2);
  border-radius: 10px;
  padding: 12px;
  background: rgba(6, 26, 68, 0.5);
}

.module-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.module-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 20px;
  background: rgba(15, 52, 118, 0.7);
  border: 1px solid rgba(91, 195, 255, 0.25);
}

.module-title {
  flex: 1;
  display: grid;
  gap: 2px;
}

.module-title h3 {
  margin: 0;
  color: #f2fbff;
  font-size: 15px;
}

.module-title span {
  font-size: 12px;
}

.module-desc {
  margin: 0 0 10px;
  color: #b8ebfb;
  font-size: 12px;
  line-height: 1.5;
}

.module-meta {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #86c7df;
}

.switch {
  position: relative;
  width: 44px;
  height: 24px;
}

.switch input {
  opacity: 0;
  width: 0;
  height: 0;
}

.slider {
  position: absolute;
  inset: 0;
  border-radius: 24px;
  background: #123a72;
  border: 1px solid rgba(91, 195, 255, 0.3);
  cursor: pointer;
  transition: 0.2s;
}

.slider::before {
  content: '';
  position: absolute;
  left: 2px;
  top: 2px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: #8dd8f1;
  transition: 0.2s;
}

.switch input:checked + .slider {
  background: #0f5e8a;
  border-color: #5cd8ff;
}

.switch input:checked + .slider::before {
  transform: translateX(20px);
  background: #5cd8ff;
}

.conn-list,
.log-list {
  display: grid;
  gap: 8px;
}

.conn-row,
.log-row {
  display: grid;
  padding: 10px;
  border-radius: 6px;
  background: rgba(8, 29, 72, 0.4);
  border: 1px solid rgba(91, 195, 255, 0.15);
  font-size: 13px;
  color: #d9f6ff;
}

.conn-row {
  grid-template-columns: 1fr 80px 70px;
}

.log-row {
  grid-template-columns: 80px 1fr;
  gap: 10px;
}

.log-row .time {
  color: #86c7df;
}

.latency {
  text-align: right;
  color: #86c7df;
}

.mt {
  margin-top: 18px;
}

.accent-green { color: #4bffa9; }
.accent-yellow { color: #ffe56b; }
.accent-pink { color: #ff87cd; }

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(2, 8, 22, 0.78);
  display: grid;
  place-items: center;
  z-index: 100;
}

.modal {
  width: 360px;
  padding: 20px;
  border-radius: 12px;
  border: 1px solid rgba(88, 203, 255, 0.5);
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.96), rgba(6, 23, 67, 0.98));
  box-shadow: 0 0 24px rgba(24, 190, 255, 0.25);
}

.modal h3 {
  margin: 0 0 14px;
  color: #f2fbff;
}

.form-row {
  margin-bottom: 12px;
  display: grid;
  gap: 6px;
}

.form-row label {
  font-size: 13px;
  color: #9edcf3;
}

.form-row input {
  height: 38px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid rgba(111, 212, 255, 0.22);
  background: rgba(8, 26, 64, 0.82);
  color: #dcf7ff;
  outline: none;
}

.modal-actions {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

@media (max-width: 1024px) {
  .screen-grid { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn { width: 100%; }
  .conn-row { grid-template-columns: 1fr; gap: 4px; }
}
</style>
