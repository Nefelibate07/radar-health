<template>
  <section class="demo-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">DIAGNOSIS QUERY CENTER</span>
        <h1>诊断查询</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">合成演示快照 · {{ source.source_type || '等待快照' }}</span>
        <button class="head-btn secondary" @click="goHome">返回主界面</button>
        <button class="head-btn" @click="search">查询</button>
      </div>
    </header>

    <article class="panel search-panel">
      <div class="form-row">
        <div class="field">
          <label>起始时间</label>
          <input v-model="filters.start" type="datetime-local" />
        </div>
        <div class="field">
          <label>结束时间</label>
          <input v-model="filters.end" type="datetime-local" />
        </div>
        <div class="field">
          <label>子系统</label>
          <select v-model="filters.system">
            <option value="">全部</option>
            <option v-for="s in SUBSYSTEMS" :key="s.id" :value="s.name">{{ s.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>故障等级</label>
          <select v-model="filters.level">
            <option value="">全部</option>
            <option>严重故障</option>
            <option>一般故障</option>
            <option>提示</option>
          </select>
        </div>
      </div>
    </article>

    <div class="screen-grid">
      <article class="panel table-panel">
        <h2>诊断结果</h2>
        <div class="row-head">
          <span>时间</span>
          <span>子系统</span>
          <span>故障等级</span>
          <span>诊断结论</span>
          <span>置信度</span>
        </div>
        <div v-for="(row, idx) in resultsWithSim" :key="idx" class="row-item">
          <span>{{ row.time }}</span>
          <span>{{ row.system }}</span>
          <span :class="levelClass(row.level)">{{ row.level }}</span>
          <span>{{ row.conclusion }}</span>
          <span>{{ row.confidence }}%</span>
        </div>
      </article>

      <article class="panel stats-panel">
        <h2>诊断统计</h2>
        <div class="stat-row">
          <span>查询记录数</span>
          <strong>{{ results.length }}</strong>
        </div>
        <div class="stat-row">
          <span>严重故障</span>
          <strong class="danger">{{ severeCount }}</strong>
        </div>
        <div class="stat-row">
          <span>一般故障</span>
          <strong class="warn">{{ generalCount }}</strong>
        </div>
        <div class="stat-row">
          <span>平均置信度</span>
          <strong class="ok">{{ avgConfidence }}%</strong>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { SUBSYSTEMS } from '../config/subsystems'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'

const router = useRouter()
const source = ref({ source_type: null })

const filters = reactive({
  start: '',
  end: '',
  system: '',
  level: ''
})

const allResults = ref([])

const results = ref([...allResults.value])

const resultsWithSim = computed(() => results.value)

const severeCount = computed(() => results.value.filter((r) => r.level === '严重故障').length)
const generalCount = computed(() => results.value.filter((r) => r.level === '一般故障').length)
const avgConfidence = computed(() => {
  if (!resultsWithSim.value.length) return 0
  return Math.round(resultsWithSim.value.reduce((s, r) => s + r.confidence, 0) / resultsWithSim.value.length)
})

const levelClass = (level) => {
  if (level === '严重故障') return 'accent-pink'
  if (level === '一般故障') return 'accent-yellow'
  return 'accent-cyan'
}

const search = () => {
  results.value = allResults.value.filter((r) => {
    const matchSystem = !filters.system || r.system === filters.system
    const matchLevel = !filters.level || r.level === filters.level
    const timestamp = r.time && r.time !== '--' ? String(r.time).replace(' ', 'T') : ''
    const matchStart = !filters.start || (timestamp && timestamp >= filters.start)
    const matchEnd = !filters.end || (timestamp && timestamp <= filters.end)
    return matchSystem && matchLevel && matchStart && matchEnd
  })
}

const goHome = () => router.push('/health')

const fetchResults = async () => {
  try {
    const response = await axios.get(`${API_PREFIX}/errors`, { params: { page: 1, page_size: 100, sort: 'DESC' } })
    const items = response.data?.items || []
    allResults.value = items.map((item) => {
      const report = item.fault_report || {}
      const level = item.error_type || report.故障程度 || '--'
      return {
        time: item.timestamp || report.故障时间 || '--',
        system: report.故障部件 || report.故障设备 || '--',
        level,
        conclusion: report.故障类型 || report.turntable_system || '协议快照检测到异常',
        confidence: report.confidence == null ? '--' : report.confidence
      }
    })
    results.value = [...allResults.value]
    source.value = { source_type: response.data?.source || 'scenario_engine' }
  } catch {
    allResults.value = []
    results.value = []
  }
}

onMounted(fetchResults)
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

.search-panel {
  margin-top: 12px;
  padding: 14px;
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
}

.form-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.field {
  display: grid;
  gap: 6px;
}

.field label {
  font-size: 12px;
  color: #9edcf3;
}

.field input,
.field select {
  height: 38px;
  padding: 0 10px;
  border-radius: 6px;
  border: 1px solid rgba(111, 212, 255, 0.22);
  background: rgba(8, 26, 64, 0.82);
  color: #dcf7ff;
  outline: none;
}

.screen-grid {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: 1fr 320px;
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
  padding: 14px;
}

.table-panel h2,
.stats-panel h2 {
  margin: 0 0 12px;
  color: #99e6ff;
  font-size: 16px;
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1.2fr 1fr 100px 1.4fr 80px;
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

.stat-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px;
  margin-bottom: 8px;
  border-radius: 8px;
  background: rgba(8, 29, 72, 0.4);
  border: 1px solid rgba(91, 195, 255, 0.15);
}

.stat-row span {
  font-size: 13px;
  color: #9edcf3;
}

.stat-row strong {
  font-size: 22px;
  color: #f0fbff;
}

.stat-row strong.ok { color: #4bffa9; }
.stat-row strong.warn { color: #ffe56b; }
.stat-row strong.danger { color: #ff87cd; }

.accent-green { color: #4bffa9; }
.accent-yellow { color: #ffe56b; }
.accent-pink { color: #ff87cd; }
.accent-cyan { color: #57eaff; }

@media (max-width: 1100px) {
  .screen-grid { grid-template-columns: 1fr; }
  .form-row { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 640px) {
  .screen-header { flex-direction: column; align-items: stretch; }
  .header-actions { width: 100%; }
  .head-btn { width: 100%; }
  .form-row { grid-template-columns: 1fr; }
  .row-head, .row-item { grid-template-columns: 1fr 1fr; }
}
</style>
