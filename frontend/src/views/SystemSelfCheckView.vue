<template>
  <section class="demo-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">SYSTEM SELF-CHECK</span>
        <h1>系统自检</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">合成演示快照 · {{ source.source_type || '等待快照' }}</span>
        <button class="head-btn secondary" @click="goHome">返回主界面</button>
        <button class="head-btn" :disabled="checking" @click="runCheck">
          {{ checking ? '自检中...' : '开始自检' }}
        </button>
      </div>
    </header>

    <div class="kpi-row">
      <article class="panel kpi-card">
        <span>自检项目</span>
        <strong>{{ checkItems.length }}</strong>
      </article>
      <article class="panel kpi-card">
        <span>通过项</span>
        <strong class="ok">{{ passedCount }}</strong>
      </article>
      <article class="panel kpi-card">
        <span>异常项</span>
        <strong class="danger">{{ failedCount }}</strong>
      </article>
    </div>

    <div class="screen-grid">
      <article class="panel progress-panel">
        <h2>总体健康度</h2>
        <div class="score-ring" :style="scoreStyle">
          <span>{{ overallScore }}</span>
        </div>
        <p class="hint">{{ errorMessage || `基于 ${checkItems.length} 项后端自检结果综合评估` }}</p>
      </article>

      <article class="panel list-panel">
        <h2>自检项目清单</h2>
        <div class="check-table">
          <div class="row-head">
            <span>子系统</span>
            <span>检查项</span>
            <span>结果说明</span>
            <span>状态</span>
          </div>
          <div
            v-for="(item, idx) in itemsWithSim"
            :key="idx"
            class="row-item"
            :class="{ running: item.status === 'running', fail: item.status === 'fail' }"
          >
            <span>{{ item.system }}</span>
            <span>{{ item.name }}</span>
          <span>{{ item.detail || '--' }}</span>
            <span :class="statusClass(item.status)">{{ statusText(item.status) }}</span>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'
import { useAuthoritySnapshot, snapshotSubsystems } from '../composables/useAuthoritySnapshot'

const router = useRouter()
const checking = ref(false)
const checkResult = ref(null)
const errorMessage = ref('')
const { health, source } = useAuthoritySnapshot()
const overallScore = computed(() => {
  // 自检按钮的返回值是一次性检查结果；场景切换后的实时健康分来自
  // ScenarioEngine 快照，必须优先使用它，避免页面继续显示旧的“正常”。
  const score = health.value.current_score ?? checkResult.value?.overall_score
  return Number.isFinite(Number(score)) ? Math.round(Number(score)) : null
})
const snapshotCheckItems = computed(() => snapshotSubsystems(health.value).map((item) => ({
  system: item.subsystem || item.name || '--',
  name: '协议快照健康状态',
  status: item.status === '正常' ? 'ok' : item.status === '故障' ? 'warn' : item.status === '报废' ? 'fail' : 'pending'
})))
const checkItems = computed(() => snapshotCheckItems.value.length ? snapshotCheckItems.value : (checkResult.value?.items || []))
const itemsWithSim = computed(() => checkItems.value)

const passedCount = computed(() => checkItems.value.filter((i) => i.status === 'ok').length)
const failedCount = computed(() => checkItems.value.filter((i) => i.status === 'fail' || i.status === 'warn').length)

const scoreStyle = computed(() => {
  const pct = overallScore.value ?? 0
  const color = pct >= 60 ? '#44f2a6' : pct >= 30 ? '#ffd365' : '#ff5b6b'
  return {
    background: `conic-gradient(${color} 0 ${pct}%, #123a72 ${pct}% 100%)`
  }
})

const statusText = (s) => ({ ok: '通过', warn: '警告', fail: '异常', running: '检测中', pending: '等待快照' }[s] || '--')
const statusClass = (s) => ({ ok: 'accent-green', warn: 'accent-yellow', fail: 'accent-pink', running: 'accent-cyan' }[s])

const runCheck = () => {
  checking.value = true
  errorMessage.value = ''
  axios.get(`${API_PREFIX}/system/self-check`)
    .then((response) => { checkResult.value = response.data.data })
    .catch((error) => { errorMessage.value = error.response?.data?.error || error.message || '自检失败' })
    .finally(() => { checking.value = false })
}

const goHome = () => router.push('/health')

onMounted(runCheck)

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

.head-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 12px rgba(89, 205, 255, 0.28);
}

.head-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
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

.kpi-row {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, 1fr);
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
  padding: 14px;
}

.kpi-card span {
  color: #8dd8f1;
  font-size: 13px;
}

.kpi-card strong {
  display: block;
  margin-top: 6px;
  font-size: 34px;
  color: #f0fbff;
}

.kpi-card strong.ok {
  color: #4bffa9;
}

.kpi-card strong.danger {
  color: #ff8f9e;
}

.screen-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: 360px 1fr;
}

.progress-panel {
  display: grid;
  place-items: center;
  align-content: start;
  gap: 16px;
}

.progress-panel h2 {
  margin: 0;
  justify-self: start;
  color: #99e6ff;
  font-size: 16px;
}

.score-ring {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 42px;
  font-weight: 700;
  color: #f2fbff;
}

.score-ring span {
  width: 120px;
  height: 120px;
  border-radius: 50%;
  background: #042557;
  display: grid;
  place-items: center;
  border: 1px solid rgba(103, 227, 255, 0.45);
}

.hint {
  margin: 0;
  color: #86c7df;
  font-size: 12px;
  text-align: center;
}

.list-panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.check-table {
  display: grid;
  gap: 6px;
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1.2fr 1.6fr 100px 80px;
  gap: 8px;
  font-size: 13px;
  padding: 8px 10px;
  border-radius: 6px;
}

.row-head {
  color: #81dfff;
  background: rgba(15, 52, 118, 0.6);
}

.row-item {
  color: #d9f6ff;
  background: rgba(8, 29, 72, 0.4);
  border: 1px solid rgba(91, 195, 255, 0.15);
}

.row-item.running {
  animation: pulseRow 1.2s infinite;
}

@keyframes pulseRow {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.accent-green { color: #4bffa9; }
.accent-yellow { color: #ffe56b; }
.accent-pink { color: #ff87cd; }
.accent-cyan { color: #57eaff; }

@media (max-width: 1024px) {
  .screen-grid { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: 1fr; }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn { width: 100%; }
  .row-head, .row-item { grid-template-columns: 1fr 1fr; }
}
</style>
