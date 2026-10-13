<template>
  <section class="demo-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">REAL-TIME STATUS MONITOR</span>
        <h1>状态监测</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">合成演示快照 · {{ source.source_type || '等待快照' }}</span>
        <button class="head-btn secondary" @click="goHome">返回主界面</button>
        <button class="head-btn" @click="refresh">刷新数据</button>
      </div>
    </header>

    <div class="kpi-row">
      <article v-for="k in kpis" :key="k.label" class="panel kpi-card">
        <span>{{ k.label }}</span>
        <strong :class="k.color">{{ k.displayValue }}</strong>
      </article>
    </div>

    <div class="screen-grid">
      <article class="panel chart-panel">
        <h2>关键指标实时曲线</h2>
        <div class="trend-wrap">
          <svg viewBox="0 0 640 220" preserveAspectRatio="none" class="trend-svg">
            <line v-for="y in [40,90,140,190]" :key="y" x1="50" :y1="y" x2="610" :y2="y" class="grid-line" />
            <line class="axis" x1="50" y1="200" x2="610" y2="200" />
            <line class="axis" x1="50" y1="20" x2="50" y2="200" />
            <polyline class="line-a" :points="pointsA" />
            <polyline class="line-b" :points="pointsB" />
            <circle v-for="(p, i) in plotPoints" :key="i" :cx="p.x" :cy="p.yA" r="3" class="dot-a" />
          </svg>
        </div>
        <div class="legend">
          <span><i class="dot" style="background:#5cd8ff"></i>历史健康度</span>
          <span><i class="dot" style="background:#ff7b8b"></i>当前快照健康度</span>
        </div>
      </article>

      <article class="panel table-panel">
        <h2>测点实时状态</h2>
        <div class="row-head">
          <span>测点名称</span>
          <span>当前值</span>
          <span>单位</span>
          <span>状态</span>
        </div>
        <div v-for="(item, idx) in telemetry" :key="idx" class="row-item">
          <span>{{ item.name }}</span>
          <span>{{ item.displayValue }}</span>
          <span>{{ item.unit }}</span>
          <span :class="item.statusClass">{{ item.status }}</span>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthoritySnapshot, snapshotParameters, formatSnapshotValue } from '../composables/useAuthoritySnapshot'

const router = useRouter()
const { health, overview, source, refresh: refreshSnapshot } = useAuthoritySnapshot()
const parameters = computed(() => snapshotParameters(health.value))
const numeric = computed(() => parameters.value.filter((item) => item.dtype !== 'enum'))

const kpis = computed(() => [
  { label: '在线测点', displayValue: parameters.value.length ? String(parameters.value.length) : '--', color: 'ok' },
  { label: '平均温度', displayValue: (() => { const xs = numeric.value.filter((p) => p.unit === '℃'); return xs.length ? `${(xs.reduce((s, p) => s + Number(p.value || 0), 0) / xs.length).toFixed(1)} ℃` : '--' })(), color: 'warn' },
  { label: '电流测点', displayValue: numeric.value.filter((p) => p.unit === 'A').length ? String(numeric.value.filter((p) => p.unit === 'A').length) : '--', color: 'ok' },
  { label: '协议采样', displayValue: source.value.sequence == null ? '--' : `序号 ${source.value.sequence}`, color: 'ok' }
])

const telemetry = computed(() => parameters.value.filter((item) => item.dtype !== 'enum').slice(0, 12).map((item) => ({
  name: item.name,
  displayValue: formatSnapshotValue(item),
  unit: item.unit || '',
  status: item.status || '--',
  statusClass: item.status === '正常' ? 'accent-green' : item.status === '故障' ? 'accent-yellow' : item.status === '报废' ? 'accent-pink' : 'accent-cyan'
})))

const history = computed(() => overview.value?.history_trend || {})
const seriesA = computed(() => Array.isArray(history.value.values) ? history.value.values : [])
const seriesB = computed(() => seriesA.value.map(() => Number(health.value.current_score) || 0))

const plotPoints = computed(() => {
  const startX = 70
  const endX = 590
  const step = seriesA.value.length > 1 ? (endX - startX) / (seriesA.value.length - 1) : 0
  return seriesA.value.map((_, i) => {
    const x = Math.round(startX + step * i)
    return {
      x,
      yA: Math.round(200 - (seriesA.value[i] / 160) * 170),
      yB: Math.round(200 - (seriesB.value[i] / 160) * 170)
    }
  })
})

const pointsA = computed(() => plotPoints.value.map((p) => `${p.x},${p.yA}`).join(' '))
const pointsB = computed(() => plotPoints.value.map((p) => `${p.x},${p.yB}`).join(' '))

const refresh = async () => {
  try {
    await refreshSnapshot()
  } catch (error) {
    console.error('刷新状态监测失败', error)
  }
}

const goHome = () => router.push('/health')

onMounted(refresh)
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

.kpi-row {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, 1fr);
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
  font-size: 30px;
  color: #f0fbff;
}

.kpi-card strong.ok { color: #4bffa9; }
.kpi-card strong.warn { color: #ffe56b; }

.screen-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: 1.4fr 1fr;
}

.chart-panel h2,
.table-panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.trend-wrap {
  background: rgba(6, 43, 91, 0.5);
  border: 1px solid rgba(83, 203, 255, 0.25);
  border-radius: 8px;
  padding: 8px;
}

.trend-svg {
  width: 100%;
  height: 200px;
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

.line-a {
  fill: none;
  stroke: #5cd8ff;
  stroke-width: 2.4;
  filter: drop-shadow(0 0 4px rgba(92, 216, 255, 0.35));
}

.line-b {
  fill: none;
  stroke: #ff7b8b;
  stroke-width: 2.4;
  stroke-dasharray: 4 4;
}

.dot-a {
  fill: #7feaff;
  stroke: #0a295a;
  stroke-width: 1.2;
}

.legend {
  margin-top: 10px;
  display: flex;
  gap: 20px;
  font-size: 12px;
  color: #bfefff;
}

.legend .dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1.4fr 1fr 80px 80px;
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

.accent-green { color: #4bffa9; }
.accent-yellow { color: #ffe56b; }
.accent-pink { color: #ff87cd; }

@media (max-width: 1100px) {
  .screen-grid { grid-template-columns: 1fr; }
  .kpi-row { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn { width: 100%; }
  .kpi-row { grid-template-columns: 1fr; }
  .row-head, .row-item { grid-template-columns: 1fr 1fr; }
}
</style>
