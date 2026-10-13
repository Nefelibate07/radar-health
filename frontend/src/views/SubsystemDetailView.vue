<template>
  <section class="detail-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">SUBSYSTEM HEALTH DETAIL</span>
        <h1>{{ subsystem?.name || '子系统详情' }}</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">合成演示快照 · {{ dashboardPayload?.scenario_record?.source_type || '等待快照' }}</span>
        <label class="algorithm-picker">健康算法
          <select v-model="selectedAlgorithm">
            <option v-for="[key, label] in algorithmOptions" :key="key" :value="key">{{ label }}（已实装）</option>
          </select>
        </label>
        <button class="head-btn secondary" @click="goBack">返回主界面</button>
      </div>
    </header>

    <div v-if="subsystem" class="screen-grid">
      <article class="panel summary-panel">
        <h2>总体状态</h2>
        <div class="summary-body">
          <div class="score-ring" :style="scoreStyle">
            <span>{{ displayHealth }}</span>
          </div>
          <div class="summary-info">
            <p>
              <span>状态评级</span>
              <strong :class="statusClass">{{ statusText }}</strong>
            </p>
            <p>
              <span>所选算法评估</span>
              <strong>{{ algorithmScoreDisplay }}</strong>
            </p>
            <p>
              <span>主要参数</span>
              <strong>{{ displayParam }}</strong>
            </p>
            <p>
              <span>监测信号数</span>
              <strong>{{ subsystem.signals.length }}</strong>
            </p>
          </div>
        </div>
      </article>

      <article class="panel chart-panel">
        <h2>健康度波动趋势</h2>
        <div class="trend-wrap">
          <svg viewBox="0 0 560 180" preserveAspectRatio="none" class="trend-svg">
            <line v-for="y in [30,70,110,150]" :key="y" x1="40" :y1="y" x2="520" :y2="y" class="grid-line" />
            <line class="axis" x1="40" y1="165" x2="520" y2="165" />
            <line class="axis" x1="40" y1="15" x2="40" y2="165" />
            <polyline class="line" :points="trendPoints" />
            <circle v-for="(p, i) in trendPointsList" :key="i" :cx="p.x" :cy="p.y" r="3" class="dot" />
          </svg>
        </div>
      </article>

      <article class="panel signals-panel">
        <h2>信号明细</h2>
        <div class="row-head">
          <span>信号名称</span>
          <span>当前值</span>
          <span>处理方法</span>
          <span>处理值</span>
          <span>阈值</span>
          <span>状态</span>
        </div>
        <div v-for="(sig, idx) in signalsWithSim" :key="idx" class="row-item">
          <span class="signal-name">{{ sig.name }}</span>
          <span>{{ sig.displayValue }} {{ sig.unit }}</span>
          <div class="process-control">
            <select
              v-if="!sig.isDiscrete"
              :value="processingMethods[sig.id] || 'none'"
              @change="e => processingMethods[sig.id] = e.target.value"
              class="process-select">
              <option value="none">不处理</option>
              <option value="smooth">时间平滑</option>
              <option value="round">取整</option>
            </select>
            <span v-else class="discrete-hint">离散量</span>
          </div>
          <span class="processed-value">{{ sig.processedValue }} {{ sig.unit }}</span>
          <span>{{ sig.threshold }} {{ sig.unit }}</span>
          <span :class="sig.statusClass">{{ sig.statusText }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { getSubsystemById } from '../config/subsystems'
import { createDashboardSocket } from '../socket/dashboardSocket'
import { scoreToStatus, scoreToClass } from '../utils/healthStatus'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'

const route = useRoute()
const router = useRouter()
const subsystem = computed(() => getSubsystemById(route.params.id))

// 存储每个信号的处理方法选择，键为稳定的信号 ID
const processingMethods = ref({})
const selectedAlgorithm = ref('kmeans')
const algorithmCatalog = ref([])
const algorithmOptions = computed(() => algorithmCatalog.value
  .filter((item) => item.implemented && ['/api/health/evaluate', '/api/health/predict'].includes(item.endpoint))
  .map((item) => [item.key, item.name]))

// 后端拓扑传播后的健康度推送，键是子系统 id；未收到快照时显示待接收状态。
const dashboardPayload = ref(null)
let dashboardSocket = null
let algorithmRefreshTimer = null

const liveParameterMap = computed(() => {
  const map = {}
  const rows = dashboardPayload.value?.data?.health?.parameters
  if (!Array.isArray(rows)) return map
  rows.forEach((row) => {
    map[row.param_id] = row
    map[row.id] = row
  })
  return map
})

const liveSubsystem = computed(() => {
  const rows = dashboardPayload.value?.data?.health?.subsystems
  if (!Array.isArray(rows)) return null
  return rows.find((row) => row.id === route.params.id) || null
})

const algorithmEvaluation = ref(null)
const algorithmPrediction = ref(null)
const loadSelectedAlgorithm = async () => {
  try {
    algorithmEvaluation.value = null
    algorithmPrediction.value = null
    const selected = algorithmCatalog.value.find((item) => item.key === selectedAlgorithm.value)
    if (selected?.endpoint === '/api/health/evaluate') {
      const response = await axios.get(`${API_PREFIX}/health/evaluate`, { params: { algorithm: selectedAlgorithm.value } })
      algorithmEvaluation.value = response.data?.data || null
    } else if (selected?.endpoint === '/api/health/predict') {
      const response = await axios.get(`${API_PREFIX}/health/predict`, { params: { algorithm: selectedAlgorithm.value } })
      algorithmPrediction.value = response.data?.data || null
    }
  } catch (error) {
    console.warn('[subsystem-detail] algorithm request failed', error)
  }
}

const displayHealth = computed(() => {
  // 详情页的“总体状态”必须和主界面的子系统卡片表示同一件事：
  // 当前场景快照中的实时拓扑健康度。算法接口返回的是所选算法的
  // 独立评估/预测结果，不能覆盖当前快照分数，否则切换到故障场景后
  // 主界面可能显示 42 分，而详情页因算法结果显示成另一分数。
  // 保留算法请求和结果供算法选择功能使用，但不混用两种业务口径。
  const score = Number(liveSubsystem.value?.score)
  return Number.isFinite(score) ? Math.round(score) : '--'
})
const algorithmScore = computed(() =>
  algorithmEvaluation.value?.subsystems?.find((item) => item.id === route.params.id)?.score
    ?? algorithmPrediction.value?.forecast?.[0]?.subsystems?.find((item) => item.id === route.params.id)?.score
)
const algorithmScoreDisplay = computed(() => {
  const score = Number(algorithmScore.value)
  return Number.isFinite(score) ? `${Math.round(score)}（${scoreToStatus(score)}）` : '--'
})
const displayParam = computed(() =>
  subsystem.value
    ? (() => {
        const signal = subsystem.value.signals[0]
        const live = signal ? (liveParameterMap.value[signal.id] || liveParameterMap.value[`${subsystem.value.id}-${signal.appendix_no}`]) : null
        return live ? `${live.display_value ?? live.value ?? '--'} ${live.unit ?? ''}`.trim() : '--'
      })()
    : '--'
)
const statusClass = computed(() =>
  Number.isFinite(Number(displayHealth.value)) ? scoreToClass(displayHealth.value) : 'status-pending'
)
const statusText = computed(() =>
  Number.isFinite(Number(displayHealth.value)) ? scoreToStatus(displayHealth.value) : '--'
)

const scoreStyle = computed(() => {
  const score = Number(displayHealth.value) || 0
  const status = scoreToStatus(score)
  const color = status === '正常' ? '#44f2a6' : status === '故障' ? '#ffd365' : '#ff5b6b'
  return {
    background: `conic-gradient(${color} 0 ${score}%, #123a72 ${score}% 100%)`
  }
})

const signalsWithSim = computed(() => {
  if (!subsystem.value) return []
  return subsystem.value.signals.map((sig, idx) => {
    const live = liveParameterMap.value[sig.id] || liveParameterMap.value[`${subsystem.value.id}-${sig.appendix_no}`]
    const value = live?.value
    const status = live?.status === '正常' ? 'ok' : live?.status === '故障' ? 'warn' : live?.status === '报废' ? 'danger' : 'pending'

    // 判断是否为离散量（枚举类型）
    const isDiscrete = sig.dtype === 'enum'

    // 计算处理值
    let processedValue = value
    if (!isDiscrete) {
      const method = processingMethods.value[sig.id] || 'none'
      if (method === 'smooth') {
        processedValue = value
      } else if (method === 'round') {
        processedValue = Number.isFinite(Number(value)) ? Math.round(Number(value)) : '--'
      }
    }

    return {
      ...sig,
      idx,
      isDiscrete,
      displayValue: live?.display_value ?? '--',
      processedValue: isDiscrete ? (live?.display_value ?? '--') : (Number.isFinite(Number(processedValue)) ? Number(processedValue).toFixed(1) : '--'),
      threshold: live?.threshold ?? '--',
      status,
      processingMethod: isDiscrete ? '离散' : (processingMethods.value[sig.id] || 'none'),
      statusClass: status === 'pending' ? 'status-pending' : scoreToClass(live?.status === '正常' ? 100 : live?.status === '故障' ? 50 : 0),
      statusText: live?.status ?? '--'
    }
  })
})

const trendHistory = ref([])
const trendPointsList = computed(() => {
  const data = trendHistory.value
  if (!data.length) return []
  const startX = 50
  const endX = 510
  const step = data.length > 1 ? (endX - startX) / (data.length - 1) : 0
  const max = Math.max(...data, 100)
  const min = Math.min(...data, 0)
  const range = Math.max(max - min, 0.001)
  return data.map((v, i) => ({
    x: Math.round(startX + step * i),
    y: Math.round(165 - ((v - min) / range) * 140)
  }))
})
const trendPoints = computed(() => trendPointsList.value.map((p) => `${p.x},${p.y}`).join(' '))

const goBack = () => router.push('/health')

const pushTrend = () => {
  const score = Number(displayHealth.value)
  if (!Number.isFinite(score)) return
  trendHistory.value.push(score)
  if (trendHistory.value.length > 24) trendHistory.value.shift()
}

watch(
  () => route.params.id,
  () => {
    trendHistory.value = []
    pushTrend()
  },
  { immediate: true }
)

let trendInterval = null

onMounted(async () => {
  try {
    const response = await axios.get(`${API_PREFIX}/algorithms/catalog`)
    algorithmCatalog.value = response.data?.data || []
    if (!algorithmOptions.value.some(([key]) => key === selectedAlgorithm.value)) {
      selectedAlgorithm.value = algorithmOptions.value[0]?.[0] || ''
    }
  } catch (error) {
    console.warn('[subsystem-detail] algorithm catalog request failed', error)
  }
  dashboardSocket = createDashboardSocket({
    onDashboardUpdate: (payload) => {
      dashboardPayload.value = payload
      if (algorithmRefreshTimer) window.clearTimeout(algorithmRefreshTimer)
      algorithmRefreshTimer = window.setTimeout(() => loadSelectedAlgorithm(), 220)
    }
  })
  trendInterval = setInterval(pushTrend, 1000)
  loadSelectedAlgorithm()
})

watch(selectedAlgorithm, loadSelectedAlgorithm)

onUnmounted(() => {
  if (trendInterval) {
    clearInterval(trendInterval)
    trendInterval = null
  }
  if (dashboardSocket) {
    dashboardSocket.disconnect()
    dashboardSocket = null
  }
  if (algorithmRefreshTimer) {
    window.clearTimeout(algorithmRefreshTimer)
    algorithmRefreshTimer = null
  }
})
</script>

<style scoped>
.detail-screen {
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

.algorithm-picker {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #a9e7ff;
  font-size: 12px;
}

.algorithm-picker select {
  min-width: 190px;
  height: 36px;
  border: 1px solid rgba(108, 216, 255, 0.36);
  border-radius: 7px;
  background: #12345f;
  color: #e6fbff;
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
  grid-template-columns: 360px 1fr;
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
  padding: 14px;
}

.panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.summary-body {
  display: grid;
  gap: 16px;
  place-items: center;
  padding: 10px 0;
}

.algo-switch {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}

.algo-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  background: linear-gradient(180deg, #19467f, #12345f);
  color: #c6ecff;
  font-size: 12px;
  cursor: pointer;
  transition: 0.2s ease;
}

.algo-btn.active {
  background: linear-gradient(180deg, #1f5cad, #153f84);
  border-color: #5cd8ff;
  color: #e6fbff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.25);
}

.score-ring {
  width: 150px;
  height: 150px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 34px;
  font-weight: 700;
  color: #f2fbff;
}

.score-ring span {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  background: #042557;
  display: grid;
  place-items: center;
  border: 1px solid rgba(103, 227, 255, 0.45);
}

.summary-info {
  width: 100%;
  display: grid;
  gap: 10px;
}

.summary-info p {
  margin: 0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px;
  border-radius: 6px;
  background: rgba(8, 29, 72, 0.4);
  border: 1px solid rgba(91, 195, 255, 0.15);
  font-size: 13px;
}

.summary-info span {
  color: #8dd8f1;
}

.summary-info strong {
  color: #e6fbff;
  font-size: 14px;
}

.status-ok { color: #4bffa9; }
.status-warn { color: #ffe56b; }
.status-danger { color: #ff87cd; }

.trend-wrap {
  background: rgba(6, 43, 91, 0.5);
  border: 1px solid rgba(83, 203, 255, 0.25);
  border-radius: 8px;
  padding: 8px;
}

.chart-panel {
  display: flex;
  flex-direction: column;
  min-height: 260px;
}

.chart-panel .trend-wrap {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
}

.trend-svg {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: block;
}

.grid-line {
  stroke: rgba(107, 209, 255, 0.12);
  stroke-width: 1;
}

.axis {
  stroke: rgba(147, 227, 255, 0.28);
  stroke-width: 1.2;
}

.line {
  fill: none;
  stroke: #5cd8ff;
  stroke-width: 2.4;
  filter: drop-shadow(0 0 4px rgba(92, 216, 255, 0.35));
}

.dot {
  fill: #7feaff;
  stroke: #0a295a;
  stroke-width: 1.2;
}

.signals-panel {
  grid-column: 1 / -1;
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1.6fr 0.9fr 1fr 0.9fr 1fr 90px;
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

.signal-name {
  font-weight: 500;
  color: #e6fbff;
}

.process-control {
  display: flex;
  align-items: center;
}

.process-select {
  width: 100%;
  padding: 4px 6px;
  background: rgba(8, 40, 100, 0.6);
  border: 1px solid rgba(90, 200, 255, 0.3);
  border-radius: 4px;
  color: #7ddcff;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.process-select:hover {
  border-color: rgba(120, 220, 255, 0.5);
  background: rgba(15, 50, 120, 0.7);
}

.process-select:focus {
  outline: none;
  border-color: #5cd8ff;
  box-shadow: 0 0 6px rgba(92, 216, 255, 0.3);
}

.processed-value {
  color: #5cd8ff;
  font-weight: 600;
}

.discrete-hint {
  color: #a8a8a8;
  font-size: 12px;
  font-style: italic;
}

@media (max-width: 1024px) {
  .screen-grid { grid-template-columns: 1fr; }
  .signals-panel { grid-column: auto; }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn, .sim-toggle { width: 100%; }
  .row-head, .row-item { grid-template-columns: 1fr 1fr; }
}
</style>
