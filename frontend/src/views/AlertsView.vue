<template>
  <section class="alert-screen">
    <header class="screen-header">
      <button class="nav-btn" @click="goBack">返回</button>
      <h1>健康评估</h1>
      <div class="header-actions">
        <span class="source-badge">合成演示快照 · 趋势快照</span>
        <button class="nav-btn ghost" :disabled="loading" @click="refreshData">
          {{ loading ? '刷新中...' : '刷新数据' }}
        </button>
        <button class="nav-btn" :disabled="reportLoading" @click="generateReport">
          {{ reportLoading ? '生成中...' : '生成健康报告' }}
        </button>
      </div>
    </header>

    <div class="top-grid">
      <article class="panel gauge-panel">
        <h2>设备健康状态</h2>
        <div class="gauge-wrap">
          <div
            class="gauge"
            :style="{
              '--pct': `${safeTodayScore}%`,
              '--gauge-color': statusColor(summary.today_score)
            }"
          >
            <div class="gauge-inner">
              <strong>{{ safeTodayScore }}</strong>
              <span>今日健康分</span>
            </div>
          </div>
          <div class="status-block">
            <p class="status-title">当前健康等级</p>
            <p class="status-text" :style="{ color: statusColor(summary.today_score) }">
              {{ statusText(summary.today_score) }}
            </p>
            <p class="status-note">
              平均健康分：<b>{{ safeAverageScore }}</b>
            </p>
          </div>
        </div>
      </article>

      <article class="panel summary-panel">
        <h2>健康度评估概览</h2>
        <div class="summary-grid">
          <div class="metric-card">
            <label>采样天数</label>
            <strong>{{ dailyScores.length }}</strong>
          </div>
          <div class="metric-card">
            <label>正常天数</label>
            <strong class="ok">{{ healthyDays }}</strong>
          </div>
          <div class="metric-card">
            <label>故障/报废天数</label>
            <strong class="warn">{{ warningDays }}</strong>
          </div>
          <div class="metric-card">
            <label>故障总次数</label>
            <strong class="danger">{{ totalFaults }}</strong>
          </div>
        </div>

        <div class="fault-bars">
          <div v-for="item in faultRank" :key="item.date" class="fault-row">
            <span>{{ item.display_date || item.date }}</span>
            <div class="track"><i :style="{ width: `${item.ratio}%` }"></i></div>
            <em>{{ item.fault_count }} 次</em>
          </div>
          <p v-if="!faultRank.length" class="empty-tip">暂无历史数据</p>
        </div>
      </article>

      <article class="panel status-panel">
        <h2>系统健康等级分布</h2>
        <div class="distribution">
          <div class="dist-item">
            <span>正常</span>
            <div class="dist-track"><i class="good" :style="{ width: `${gradeRates.good}%` }"></i></div>
            <em>{{ gradeCounts.good }}</em>
          </div>
          <div class="dist-item">
            <span>故障</span>
            <div class="dist-track"><i class="fair" :style="{ width: `${gradeRates.fair}%` }"></i></div>
            <em>{{ gradeCounts.fair }}</em>
          </div>
          <div class="dist-item">
            <span>报废</span>
            <div class="dist-track"><i class="poor" :style="{ width: `${gradeRates.poor}%` }"></i></div>
            <em>{{ gradeCounts.poor }}</em>
          </div>
        </div>

        <div class="health-legend">
          <p>最近一周趋势：<b>{{ trendDirection }}</b></p>
          <p>最高分：<b>{{ maxScore }}</b></p>
          <p>最低分：<b>{{ minScore }}</b></p>
          <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
        </div>
      </article>
    </div>

    <div class="bottom-grid">
      <article class="panel chart-panel trend-panel">
        <h2>健康度变化趋势</h2>
        <svg viewBox="0 0 680 260" preserveAspectRatio="none">
          <g class="grid-lines">
            <line v-for="y in [40, 80, 120, 160, 200]" :key="`g-${y}`" x1="60" :y1="y" x2="650" :y2="y" />
          </g>
          <line class="axis" x1="60" y1="220" x2="650" y2="220" />
          <line class="axis" x1="60" y1="20" x2="60" y2="220" />

          <polyline v-if="trendPolyline" class="score-line" :points="trendPolyline" />
          <polyline v-if="faultPolyline" class="fault-line" :points="faultPolyline" />

          <g v-for="(p, idx) in plotPoints" :key="`p-${idx}`">
            <circle class="score-dot" :cx="p.x" :cy="p.yScore" r="4" />
            <circle class="fault-dot" :cx="p.x" :cy="p.yFault" r="3.5" />
            <text class="score-label" :x="p.x" :y="p.yScore - 10">{{ p.score }}</text>
            <text class="fault-label" :x="p.x" :y="p.yFault + 16">{{ p.fault_count }}</text>
            <text class="x-label" :x="p.x" y="242">{{ shortDate(p.display_date || p.date) }}</text>
          </g>
        </svg>
      </article>

      <article class="panel chart-panel list-panel">
        <h2>健康监测记录表</h2>
        <div class="table-head">
          <span>日期</span>
          <span>健康分</span>
          <span>等级</span>
          <span>故障次数</span>
        </div>
        <div class="table-body">
          <div v-for="row in dailyScores" :key="row.date" class="table-row">
            <span>{{ row.display_date || row.date }}</span>
            <span>{{ row.score }}</span>
            <span :class="['level-pill', levelClass(row.score)]">{{ statusText(row.score) }}</span>
            <span>{{ row.fault_count }}</span>
          </div>
          <div v-if="!dailyScores.length && !loading" class="table-empty">暂无记录</div>
          <div v-if="loading" class="table-empty">数据加载中...</div>
        </div>
      </article>
    </div>

    <div class="category-grid">
      <article class="panel category-panel">
        <h2>各子系统健康度</h2>
        <div class="category-cards">
          <div
            v-for="item in subsystemScores"
            :key="item.id"
            class="category-card"
            :style="{ '--score-color': radarColor(item.score) }"
          >
            <span class="category-name">{{ item.subsystem }}</span>
            <strong class="category-score" :style="{ color: radarColor(item.score) }">{{ Math.round(item.score) }}</strong>
            <span class="category-status">{{ item.status || '--' }}</span>
          </div>
          <p v-if="!subsystemScores.length" class="empty-tip">暂无子系统健康数据</p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'
import { createDashboardSocket } from '../socket/dashboardSocket'
import { scoreToStatus } from '../utils/healthStatus'

const router = useRouter()

const dailyScores = ref([])
const summary = ref({ today_score: null, average_score: null })
const loading = ref(false)
const reportLoading = ref(false)
const errorMessage = ref('')
const dashboardPayload = ref(null)
let dashboardSocket = null

const clamp = (value, min, max) => Math.min(max, Math.max(min, Number(value) || 0))

const safeTodayScore = computed(() => summary.value.today_score == null ? '--' : Math.round(clamp(summary.value.today_score, 0, 100)))
const safeAverageScore = computed(() => summary.value.average_score == null ? '--' : Math.round(clamp(summary.value.average_score, 0, 100)))

// good/fair/poor 只是内部字段名（沿用既有的 CSS 类名 .good/.fair/.poor)，
// 语义上对应统一后的 正常/故障/报废（60/30 阈值，utils/healthStatus.js）
const gradeCounts = computed(() => {
  const base = { good: 0, fair: 0, poor: 0 }
  dailyScores.value.forEach((item) => {
    const score = Number(item.score) || 0
    if (score >= 60) base.good += 1
    else if (score >= 30) base.fair += 1
    else base.poor += 1
  })
  return base
})

const gradeRates = computed(() => {
  const total = dailyScores.value.length || 1
  const counts = gradeCounts.value
  return {
    good: Math.round((counts.good / total) * 100),
    fair: Math.round((counts.fair / total) * 100),
    poor: Math.round((counts.poor / total) * 100)
  }
})

const healthyDays = computed(() => gradeCounts.value.good)
const warningDays = computed(() => gradeCounts.value.fair + gradeCounts.value.poor)
const totalFaults = computed(() =>
  dailyScores.value.reduce((sum, item) => sum + (Number(item.fault_count) || 0), 0)
)

const maxScore = computed(() => {
  if (!dailyScores.value.length) return '--'
  return Math.max(...dailyScores.value.map((item) => Number(item.score) || 0))
})

const minScore = computed(() => {
  if (!dailyScores.value.length) return '--'
  return Math.min(...dailyScores.value.map((item) => Number(item.score) || 0))
})

const trendDirection = computed(() => {
  if (dailyScores.value.length < 2) return '数据不足'
  const first = Number(dailyScores.value[0].score) || 0
  const last = Number(dailyScores.value[dailyScores.value.length - 1].score) || 0
  if (last > first) return '上升'
  if (last < first) return '下降'
  return '持平'
})

const faultRank = computed(() => {
  const list = dailyScores.value
    .map((item) => ({
      ...item,
      fault_count: Number(item.fault_count) || 0
    }))
    .sort((a, b) => b.fault_count - a.fault_count)
    .slice(0, 5)
  const maxFault = Math.max(1, ...list.map((item) => item.fault_count))
  return list.map((item) => ({
    ...item,
    ratio: Math.round((item.fault_count / maxFault) * 100)
  }))
})

const plotPoints = computed(() => {
  const list = dailyScores.value.slice(0, 7)
  if (!list.length) return []

  const startX = 90
  const endX = 620
  const step = list.length === 1 ? 0 : (endX - startX) / (list.length - 1)
  const maxFault = Math.max(1, ...list.map((item) => Number(item.fault_count) || 0))

  return list.map((item, index) => {
    const score = clamp(item.score, 0, 100)
    const fault = clamp(item.fault_count, 0, maxFault)
    return {
      ...item,
      score: Math.round(score),
      fault_count: Math.round(fault),
      x: Math.round(startX + step * index),
      yScore: Math.round(220 - score * 1.9),
      yFault: Math.round(220 - (fault / maxFault) * 180)
    }
  })
})

const trendPolyline = computed(() =>
  plotPoints.value.length ? plotPoints.value.map((p) => `${p.x},${p.yScore}`).join(' ') : ''
)

const faultPolyline = computed(() =>
  plotPoints.value.length ? plotPoints.value.map((p) => `${p.x},${p.yFault}`).join(' ') : ''
)

const statusText = (score) => scoreToStatus(score)

const statusColor = (score) => {
  const status = scoreToStatus(score)
  if (status === '正常') return '#44f2a6'
  if (status === '故障') return '#ffd75e'
  return '#ff6a7b'
}

const levelClass = (score) => {
  const status = scoreToStatus(score)
  if (status === '正常') return 'good'
  if (status === '故障') return 'fair'
  return 'poor'
}

const shortDate = (value) => {
  if (!value) return '--'
  const s = String(value)
  return s.includes('-') ? s.slice(5) : s
}

// 阈值和其余处对齐（60/30），不再单独用 90 的分界
const radarColor = (score) => {
  const status = scoreToStatus(score)
  if (status === '报废') return '#ff5d6f'
  if (status === '故障') return '#ffd45f'
  return '#46f2ad'
}

const healthLive = computed(() => dashboardPayload.value?.data?.health ?? {})
const subsystemScores = computed(() => Array.isArray(healthLive.value.subsystems) ? healthLive.value.subsystems : [])

const refreshData = async () => {
  loading.value = true
  errorMessage.value = ''
  try {
    const res = await axios.get(`${API_PREFIX}/health/daily-report`)
    dailyScores.value = Array.isArray(res.data?.data) ? res.data.data : []
    summary.value = res.data?.summary || { today_score: null, average_score: null }
  } catch (error) {
    errorMessage.value = '健康监测数据加载失败'
    console.error('加载健康监测数据失败', error)
  } finally {
    loading.value = false
  }
}

const generateReport = async () => {
  if (!dailyScores.value.length) {
    errorMessage.value = '暂无健康快照，无法生成报告'
    return
  }
  reportLoading.value = true
  try {
    const start = dailyScores.value[0].date
    const end = dailyScores.value[dailyScores.value.length - 1].date
    const response = await axios.get(`${API_PREFIX}/export/docx`, {
      params: { start, end, algorithm: 'current_snapshot' },
      responseType: 'blob'
    })
    if (response.data.type === 'application/json') {
      const text = await response.data.text()
      const body = JSON.parse(text)
      throw new Error(body.error || '报告生成失败')
    }
    const url = window.URL.createObjectURL(response.data)
    const link = document.createElement('a')
    link.href = url
    link.download = `HealthAssessment_${new Date().toISOString().slice(0, 10)}.docx`
    document.body.appendChild(link)
    link.click()
    window.setTimeout(() => { document.body.removeChild(link); window.URL.revokeObjectURL(url) }, 200)
  } catch (error) {
    errorMessage.value = error.message || '报告生成失败'
  } finally {
    reportLoading.value = false
  }
}

const connectDashboard = () => {
  dashboardSocket = createDashboardSocket({
    onDashboardUpdate: (payload) => {
      dashboardPayload.value = payload
      // 今日健康卡片原先只在进入页面时读取 daily-report，切换 1–5
      // 后仍会显示旧分数。实时快照是当前权威值，立即同步概览和最后一行。
      const liveScore = Number(payload?.data?.health?.current_score)
      if (Number.isFinite(liveScore)) {
        summary.value = { ...summary.value, today_score: liveScore }
        if (dailyScores.value.length) {
          const lastIndex = dailyScores.value.length - 1
          dailyScores.value[lastIndex] = {
            ...dailyScores.value[lastIndex],
            score: liveScore,
            status: payload?.data?.health?.overall_status || scoreToStatus(liveScore),
            fault_count: liveScore < 60 ? 1 : 0,
            sequence: payload?.scenario_record?.sequence ?? dailyScores.value[lastIndex].sequence,
            date: payload?.scenario_record?.timestamp || dailyScores.value[lastIndex].date
          }
        }
      }
    }
  })
}

const goBack = () => {
  router.push('/health')
}

onMounted(() => {
  refreshData()
  connectDashboard()
})

onUnmounted(() => {
  if (dashboardSocket) {
    dashboardSocket.disconnect()
    dashboardSocket = null
  }
})
</script>

<style scoped>
:root {
  --bg-1: #07153e;
  --bg-2: #0a2e73;
  --bg-3: #071a50;
  --line: rgba(83, 199, 255, 0.52);
  --line-soft: rgba(83, 199, 255, 0.2);
  --text-main: #d8f4ff;
  --text-dim: #9cdcf2;
}

.alert-screen {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  min-height: calc(100vh - 20px);
  padding: 12px;
  color: var(--text-main);
  border: 1px solid rgba(63, 203, 255, 0.55);
  border-radius: 14px;
  background:
    radial-gradient(1200px 500px at 50% -100px, rgba(95, 157, 255, 0.22), transparent 70%),
    radial-gradient(900px 420px at 92% 4%, rgba(39, 206, 255, 0.14), transparent 72%),
    radial-gradient(700px 360px at 8% 12%, rgba(114, 126, 255, 0.1), transparent 72%),
    linear-gradient(180deg, #061237 0%, #09245c 46%, #07194a 100%);
  box-shadow:
    inset 0 0 44px rgba(14, 123, 224, 0.22),
    inset 0 0 120px rgba(12, 36, 96, 0.24),
    0 12px 34px rgba(5, 18, 52, 0.45),
    0 0 20px rgba(13, 177, 255, 0.22);
}

.alert-screen::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(rgba(97, 188, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(97, 188, 255, 0.08) 1px, transparent 1px);
  background-size: 34px 34px;
}

.alert-screen::after {
  content: "";
  position: absolute;
  inset: 10px;
  border-radius: 10px;
  border: 1px solid rgba(102, 212, 255, 0.12);
  pointer-events: none;
}

.screen-header {
  position: relative;
  display: grid;
  grid-template-columns: 120px 1fr auto;
  gap: 10px;
  align-items: center;
  padding: 6px;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(10, 34, 82, 0.7), rgba(8, 24, 63, 0.68));
  border: 1px solid rgba(88, 203, 255, 0.18);
  box-shadow: inset 0 0 18px rgba(57, 160, 255, 0.08);
}

.screen-header h1 {
  margin: 0;
  text-align: center;
  position: relative;
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(113, 201, 255, 0.07), transparent 25%, transparent 75%, rgba(113, 201, 255, 0.07)),
    linear-gradient(180deg, #143e8a, #102f6f);
  border: 1px solid rgba(88, 212, 255, 0.32);
  border-radius: 10px;
  color: #ffffff;
  font-size: 34px;
  letter-spacing: 4px;
  padding: 12px 0;
  text-shadow: 0 0 14px rgba(255, 102, 102, 0.45);
  box-shadow:
    inset 0 0 18px rgba(74, 164, 255, 0.2),
    inset 0 -8px 18px rgba(6, 17, 48, 0.28),
    0 0 12px rgba(38, 177, 255, 0.16);
}

.screen-header h1::before,
.screen-header h1::after {
  content: "";
  position: absolute;
  top: 50%;
  width: 36px;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(135, 231, 255, 0.7), transparent);
}

.screen-header h1::before {
  left: 12px;
}

.screen-header h1::after {
  right: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.nav-btn {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(110, 220, 255, 0.28);
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.05), transparent 40%),
    linear-gradient(180deg, #2a61bf, #1d468f);
  color: #e6f8ff;
  font-size: 16px;
  border-radius: 10px;
  padding: 9px 12px;
  transition: all 0.2s ease;
  cursor: pointer;
  box-shadow:
    inset 0 0 10px rgba(83, 184, 255, 0.12),
    0 4px 10px rgba(7, 20, 55, 0.22);
}

.nav-btn:hover:not(:disabled) {
  border-color: #8ce6ff;
  transform: translateY(-1px);
  box-shadow:
    inset 0 0 12px rgba(109, 223, 255, 0.16),
    0 0 14px rgba(98, 213, 255, 0.24),
    0 8px 16px rgba(7, 26, 73, 0.28);
}

.nav-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.sim-toggle {
  padding: 9px 12px;
  border-radius: 10px;
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

.nav-btn.ghost {
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.04), transparent 45%),
    linear-gradient(180deg, #1a437f, #133362);
}

.panel {
  position: relative;
  border-radius: 12px;
  border: 1px solid rgba(94, 206, 255, 0.28);
  background:
    linear-gradient(180deg, rgba(8, 40, 102, 0.82), rgba(7, 27, 79, 0.88)),
    radial-gradient(circle at 10% 0%, rgba(86, 170, 255, 0.08), transparent 55%);
  box-shadow:
    inset 0 0 22px rgba(30, 171, 255, 0.12),
    inset 0 -14px 24px rgba(5, 15, 44, 0.24),
    0 8px 16px rgba(7, 22, 58, 0.2);
  padding: 14px;
  backdrop-filter: blur(4px);
  transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.panel::after {
  content: "";
  position: absolute;
  inset: 5px;
  border: 1px solid rgba(106, 212, 255, 0.09);
  border-radius: 10px;
  pointer-events: none;
}

.panel::before {
  content: "";
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border-top: 1px solid rgba(117, 224, 255, 0.22);
  border-right: 1px solid rgba(117, 224, 255, 0.22);
  opacity: 0.8;
  pointer-events: none;
}

.panel:hover {
  transform: translateY(-1px);
  border-color: rgba(124, 224, 255, 0.36);
  box-shadow:
    inset 0 0 22px rgba(30, 171, 255, 0.16),
    0 12px 22px rgba(7, 25, 68, 0.28);
}

h2 {
  margin: 0 0 10px;
  display: inline-block;
  padding: 5px 12px;
  font-size: 16px;
  font-weight: 600;
  color: #9ce9ff;
  border: 1px solid rgba(96, 206, 255, 0.22);
  background:
    linear-gradient(90deg, rgba(122, 223, 255, 0.09), rgba(122, 223, 255, 0)),
    linear-gradient(180deg, rgba(28, 85, 170, 0.76), rgba(18, 54, 113, 0.82));
  border-radius: 8px;
  box-shadow: inset 0 0 8px rgba(96, 206, 255, 0.08);
}

.top-grid {
  margin-top: 10px;
  display: grid;
  gap: 10px;
  grid-template-columns: 1.05fr 1.45fr 1fr;
}

.bottom-grid {
  margin-top: 10px;
  display: grid;
  gap: 10px;
  grid-template-columns: 1.5fr 1fr;
}

.gauge-wrap {
  display: grid;
  grid-template-columns: 180px 1fr;
  gap: 14px;
  align-items: center;
  min-height: 220px;
}

.gauge {
  --pct: 0%;
  --gauge-color: #44f2a6;
  position: relative;
  width: 160px;
  height: 160px;
  margin: 0 auto;
  border-radius: 50%;
  background:
    radial-gradient(circle at 50% 50%, rgba(4, 18, 50, 0.92) 52%, transparent 53%),
    conic-gradient(var(--gauge-color) 0 var(--pct), rgba(255, 255, 255, 0.12) var(--pct) 100%);
  box-shadow:
    inset 0 0 24px rgba(72, 186, 255, 0.18),
    inset 0 -18px 18px rgba(4, 15, 44, 0.28),
    0 0 16px rgba(35, 170, 255, 0.16);
}

.gauge::before {
  content: "";
  position: absolute;
  inset: 12px;
  border-radius: 50%;
  border: 1px solid rgba(124, 220, 255, 0.26);
}

.gauge::after {
  content: "";
  position: absolute;
  inset: -8px;
  border-radius: 50%;
  border: 1px dashed rgba(119, 225, 255, 0.16);
}

.gauge-inner {
  position: absolute;
  inset: 26px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  align-content: center;
  background: radial-gradient(circle, rgba(16, 45, 98, 0.88), rgba(5, 20, 58, 0.92));
  text-align: center;
}

.gauge-inner strong {
  font-size: 38px;
  line-height: 1;
  color: #dcf8ff;
  text-shadow: 0 0 10px rgba(105, 223, 255, 0.35);
}

.gauge-inner span {
  margin-top: 4px;
  font-size: 12px;
  color: var(--text-dim);
}

.status-block {
  padding: 10px;
  border: 1px solid rgba(100, 205, 255, 0.14);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(10, 31, 82, 0.48), rgba(7, 24, 67, 0.38));
  box-shadow: inset 0 0 12px rgba(87, 196, 255, 0.06);
}

.status-title {
  margin: 0 0 6px;
  color: #eefbff;
  font-size: 13px;
}

.status-text {
  margin: 0 0 10px;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: 2px;
  text-shadow: 0 0 12px rgba(255, 255, 255, 0.12);
}

.status-note {
  margin: 0;
  color: #bcefff;
  font-size: 14px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 14px;
}

.metric-card {
  min-height: 70px;
  border-radius: 10px;
  padding: 8px 10px;
  border: 1px solid rgba(99, 206, 255, 0.14);
  background:
    linear-gradient(180deg, rgba(8, 32, 76, 0.78), rgba(9, 23, 56, 0.9)),
    radial-gradient(circle at 0 0, rgba(93, 196, 255, 0.08), transparent 55%);
  display: grid;
  align-content: center;
  gap: 4px;
  box-shadow: inset 0 0 8px rgba(88, 199, 255, 0.05);
}

.metric-card label {
  color: #eefbff;
  font-size: 12px;
}

.metric-card strong {
  font-size: 22px;
  color: #ddf7ff;
}

.metric-card strong.ok {
  color: #44f2a6;
}

.metric-card strong.warn {
  color: #ffd75e;
}

.metric-card strong.danger {
  color: #ff6a7b;
}

.fault-bars {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(99, 206, 255, 0.1);
  background: rgba(5, 20, 56, 0.28);
}

.fault-row {
  display: grid;
  grid-template-columns: 90px 1fr 52px;
  gap: 8px;
  align-items: center;
  color: #cdefff;
  font-size: 13px;
}

.fault-row .track {
  height: 10px;
  border-radius: 999px;
  border: 1px solid rgba(123, 218, 255, 0.18);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0.02));
  overflow: hidden;
}

.fault-row .track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #34d6ff, #4f93ff 45%, #7e66ff);
  box-shadow:
    inset 0 0 10px rgba(255, 255, 255, 0.12),
    0 0 8px rgba(111, 164, 255, 0.2);
}

.fault-row em {
  font-style: normal;
  color: #97e8ff;
  text-align: right;
}

.empty-tip {
  margin: 6px 0 0;
  color: #8bbcd0;
  font-size: 13px;
}

.distribution {
  display: grid;
  gap: 12px;
  margin: 8px 0 14px;
  padding: 10px;
  border-radius: 10px;
  border: 1px solid rgba(103, 204, 255, 0.1);
  background: rgba(8, 25, 68, 0.24);
}

.dist-item {
  display: grid;
  grid-template-columns: 20px 1fr 28px;
  align-items: center;
  gap: 8px;
  color: #eefbff;
}

.dist-track {
  height: 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(118, 220, 255, 0.12);
  overflow: hidden;
}

.dist-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
}

.dist-track i.good {
  background: linear-gradient(90deg, #2fd4a5, #67ffcd);
}

.dist-track i.fair {
  background: linear-gradient(90deg, #ffd365, #ffb34d);
}

.dist-track i.poor {
  background: linear-gradient(90deg, #ff5b6b, #ff8fa2);
}

.dist-item em {
  font-style: normal;
  color: #9fe6ff;
  text-align: right;
}

.health-legend {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 8px;
  border: 1px solid rgba(111, 204, 255, 0.12);
  background:
    linear-gradient(180deg, rgba(6, 21, 58, 0.55), rgba(6, 21, 58, 0.38));
  color: #bfefff;
  font-size: 13px;
  box-shadow: inset 0 0 12px rgba(84, 193, 255, 0.06);
}

.health-legend p {
  margin: 0;
}

.health-legend b {
  color: #fff0a0;
}

.error-text {
  color: #ff8f9d;
}

.category-grid {
  margin-top: 10px;
}

.category-panel {
  background:
    linear-gradient(180deg, rgba(8, 34, 87, 0.82), rgba(7, 23, 65, 0.9)),
    radial-gradient(circle at 20% 0%, rgba(98, 146, 255, 0.15), transparent 55%);
}

.category-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 10px;
  margin-top: 6px;
  max-height: 420px;
  overflow-y: auto;
  padding-right: 4px;
}

.category-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--score-color) 45%, rgba(99, 206, 255, 0.14));
  background:
    linear-gradient(180deg, rgba(8, 32, 76, 0.78), rgba(9, 23, 56, 0.9));
  box-shadow: inset 0 0 8px rgba(88, 199, 255, 0.05);
}

.category-name {
  color: #eefbff;
  font-size: 13px;
}

.category-score {
  font-size: 26px;
  font-weight: 700;
}

.category-status {
  color: #9fe6ff;
  font-size: 12px;
}

.chart-panel {
  min-height: 320px;
  background:
    linear-gradient(180deg, rgba(8, 34, 87, 0.82), rgba(7, 23, 65, 0.9)),
    radial-gradient(circle at 90% 0%, rgba(121, 115, 255, 0.06), transparent 48%);
}

.trend-panel svg {
  width: 100%;
  height: 260px;
  display: block;
  padding: 4px;
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(6, 21, 57, 0.25), rgba(6, 21, 57, 0.12));
}

.grid-lines line {
  stroke: rgba(107, 209, 255, 0.1);
  stroke-width: 1;
}

.axis {
  stroke: rgba(147, 227, 255, 0.28);
  stroke-width: 1.2;
}

.score-line {
  fill: none;
  stroke: #5cd8ff;
  stroke-width: 2.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  filter: drop-shadow(0 0 5px rgba(92, 216, 255, 0.35));
}

.fault-line {
  fill: none;
  stroke: #ff7b8b;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 4 4;
}

.score-dot {
  fill: #7feaff;
  stroke: #0a295a;
  stroke-width: 1.4;
}

.fault-dot {
  fill: #ff7f8d;
  stroke: #401126;
  stroke-width: 1.2;
}

.score-label,
.fault-label,
.x-label {
  fill: #bfefff;
  font-size: 12px;
  text-anchor: middle;
}

.fault-label {
  fill: #ff9cab;
}

.x-label {
  fill: #9fdaf0;
}

.list-panel {
  display: grid;
  grid-template-rows: auto auto 1fr;
}

.table-head,
.table-row {
  display: grid;
  grid-template-columns: 1.3fr 0.8fr 0.8fr 0.8fr;
  gap: 8px;
  align-items: center;
}

.table-head {
  padding: 10px 10px;
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(31, 84, 160, 0.24), rgba(18, 53, 112, 0.22));
  border: 1px solid rgba(103, 204, 255, 0.12);
  color: #aeeeff;
  font-size: 13px;
  box-shadow: inset 0 0 8px rgba(103, 204, 255, 0.06);
}

.table-body {
  margin-top: 8px;
  display: grid;
  gap: 8px;
  align-content: start;
  max-height: 248px;
  overflow: auto;
  padding-right: 4px;
  padding-top: 2px;
}

.table-body::-webkit-scrollbar {
  width: 6px;
}

.table-body::-webkit-scrollbar-thumb {
  background: rgba(92, 199, 255, 0.35);
  border-radius: 999px;
}

.table-row {
  padding: 8px 10px;
  border-radius: 10px;
  border: 1px solid rgba(104, 202, 255, 0.09);
  background:
    linear-gradient(180deg, rgba(7, 25, 64, 0.5), rgba(6, 19, 50, 0.42));
  color: #d0f4ff;
  font-size: 13px;
  transition: border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}

.table-row:nth-child(2n) {
  background:
    linear-gradient(180deg, rgba(8, 28, 72, 0.55), rgba(6, 20, 52, 0.46));
}

.table-row:hover {
  transform: translateY(-1px);
  border-color: rgba(114, 217, 255, 0.18);
  background:
    linear-gradient(180deg, rgba(10, 34, 84, 0.6), rgba(7, 24, 59, 0.52));
}

.level-pill {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 42px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.06);
}

.level-pill.good {
  color: #64ffc7;
  border-color: rgba(100, 255, 199, 0.25);
}

.level-pill.fair {
  color: #ffe07f;
  border-color: rgba(255, 224, 127, 0.25);
}

.level-pill.poor {
  color: #ff95a3;
  border-color: rgba(255, 149, 163, 0.25);
}

.table-empty {
  padding: 18px 12px;
  text-align: center;
  color: #8dbed4;
  border: 1px dashed rgba(117, 214, 255, 0.18);
  border-radius: 8px;
  background: rgba(7, 23, 56, 0.2);
}

@media (max-width: 1200px) {
  .top-grid {
    grid-template-columns: 1fr;
  }

  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 860px) {
  .screen-header {
    grid-template-columns: 1fr;
  }

  .screen-header h1 {
    font-size: 24px;
    letter-spacing: 2px;
  }

  .header-actions {
    width: 100%;
    justify-content: stretch;
  }

  .header-actions .nav-btn {
    flex: 1;
  }

  .gauge-wrap {
    grid-template-columns: 1fr;
  }

  .fault-row {
    grid-template-columns: 78px 1fr 44px;
  }

  .table-head,
  .table-row {
    grid-template-columns: 1.3fr 0.7fr 0.7fr 0.7fr;
    font-size: 12px;
  }
}
</style>
