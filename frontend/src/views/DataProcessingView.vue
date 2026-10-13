<template>
  <section class="processing-screen">
    <header class="screen-header">
      <div>
        <span class="eyebrow">SIGNAL PROCESSING CENTER</span>
        <h1>数据处理</h1>
        <p>按测点类别配置算法，并查看实时原始值、处理值与阈值状态。</p>
      </div>
      <div class="header-actions">
        <span class="source-badge" :class="connected ? 'online' : ''">{{ connected ? '实时数据已连接' : '等待实时数据' }} · {{ snapshot.mode_label || '场景数据' }}</span>
        <button class="head-btn" :disabled="saving" @click="saveAll">{{ saving ? '保存中…' : '保存配置' }}</button>
        <button class="head-btn secondary" @click="router.push('/health')">返回主界面</button>
      </div>
    </header>

    <div class="summary-grid">
      <article class="summary-card"><span>测点总数</span><strong>{{ signals.length }}</strong></article>
      <article class="summary-card"><span>数值量</span><strong>{{ numericCount }}</strong></article>
      <article class="summary-card"><span>离散量</span><strong>{{ discreteCount }}</strong></article>
      <article class="summary-card"><span>待配置阈值</span><strong class="warn-text">{{ unconfiguredCount }}</strong></article>
    </div>

    <nav class="view-tabs" aria-label="数据处理视图">
      <button :class="{ active: activeTab === 'signals' }" @click="activeTab = 'signals'">测点处理总览</button>
      <button :class="{ active: activeTab === 'categories' }" @click="activeTab = 'categories'">类别算法配置</button>
    </nav>

    <template v-if="activeTab === 'signals'">
      <div class="filter-bar">
        <label>关键词<input v-model.trim="keyword" placeholder="测点名称或编号" /></label>
        <label>子系统<select v-model="subsystemFilter"><option value="">全部子系统</option><option v-for="item in subsystems" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label>数据类别<select v-model="categoryFilter"><option value="">全部类别</option><option v-for="item in categories" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
        <label>状态<select v-model="statusFilter"><option value="">全部状态</option><option>正常</option><option>越限</option><option>状态告警</option><option>待配置阈值</option><option>无数据</option></select></label>
        <span class="result-count">显示 {{ pagedSignals.length }} / {{ filteredSignals.length }} 条</span>
      </div>

      <article class="panel table-panel">
        <div class="panel-heading">
          <div><h2>实时测点处理</h2><p>参数分类默认根据 config/params.json 中的类型和单位自动识别，可逐行更改。</p></div>
          <span class="timestamp">快照 {{ snapshot.timestamp || '--' }} · #{{ snapshot.sequence ?? '--' }}</span>
        </div>
        <div class="table-scroll">
          <table>
            <thead><tr><th>信号名称</th><th>当前值</th><th>数据类别</th><th>处理方法</th><th>处理值</th><th>阈值范围</th><th>状态</th></tr></thead>
            <tbody>
              <tr v-for="signal in pagedSignals" :key="signal.id">
                <td><strong>{{ signal.name }}</strong><small>{{ signal.id }} · {{ signal.subsystem }}</small></td>
                <td>{{ signal.current_display }} <small class="unit">{{ signal.unit }}</small></td>
                <td><select class="inline-select" :value="categoryDraft[signal.id] || 'auto'" @change="setSignalCategory(signal.id, $event.target.value)"><option value="auto">自动 · {{ signal.category_name }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></td>
              <td>{{ effectiveMethodName(signal) }}<small v-if="effectiveMethod(signal) !== 'none'">窗口 {{ methodWindow(effectiveCategory(signal)) }}</small></td>
                <td class="processed-value">{{ signal.processed_display }} <small class="unit">{{ signal.unit }}</small></td>
                <td>
                  <template v-if="signal.dtype === 'enum'"><span class="enum-threshold">按状态枚举</span></template>
                  <template v-else>
                    <div class="threshold-editor">
                      <input type="number" step="any" :aria-label="`${signal.name}阈值下限`" placeholder="下限" :value="thresholdValue(signal, 'minimum')" @input="editThreshold(signal, 'minimum', $event.target.value)" />
                      <span>—</span>
                      <input type="number" step="any" :aria-label="`${signal.name}阈值上限`" placeholder="上限" :value="thresholdValue(signal, 'maximum')" @input="editThreshold(signal, 'maximum', $event.target.value)" />
                    </div>
                    <small>{{ thresholdSource(signal) }}</small>
                  </template>
                </td>
                <td><span class="status-pill" :class="statusClass(signal.severity)">{{ signal.status }}</span></td>
              </tr>
              <tr v-if="!pagedSignals.length"><td colspan="7" class="empty-state">没有匹配的测点</td></tr>
            </tbody>
          </table>
        </div>
        <footer class="pagination"><button :disabled="page <= 1" @click="page--">上一页</button><span>第 {{ page }} / {{ pageCount }} 页</span><button :disabled="page >= pageCount" @click="page++">下一页</button></footer>
      </article>
    </template>

    <template v-else>
      <div class="category-layout">
        <article class="panel category-list"><h2>数据类别</h2><button v-for="category in categories" :key="category.id" :class="{ active: selectedCategory === category.id }" @click="selectedCategory = category.id"><span>{{ category.name }}</span><small>{{ categoryCounts[category.id] || 0 }} 个测点</small></button></article>
        <article class="panel category-editor" v-if="activeCategory">
          <span class="eyebrow">CLASS BASED PROCESSING</span>
          <h2>{{ activeCategory.name }}处理规则</h2>
          <p>规则应用于当前归入此类别的全部测点；单个测点仍可在总览页修改类别或阈值。</p>
          <label class="form-field">处理算法<select v-model="categoryDraftSettings[activeCategory.id].method"><option v-for="method in methodsFor(activeCategory)" :key="method.id" :value="method.id">{{ method.name }}</option></select></label>
          <div class="form-columns">
            <label class="form-field">滤波窗口<input v-model.number="categoryDraftSettings[activeCategory.id].window" type="number" min="1" max="101" @input="clearError" /><small>请输入 1–101 之间的整数，当前默认窗口为 5。</small></label>
            <label v-if="categoryDraftSettings[activeCategory.id].method === 'exponential'" class="form-field">平滑系数 α<input v-model.number="categoryDraftSettings[activeCategory.id].alpha" type="number" min="0.01" max="1" step="0.01" @input="clearError" /><small>请输入 0.01–1 之间的数值；数值越大越贴近最新样本。</small></label>
          </div>
          <div class="rule-note"><strong>算法说明</strong><span>{{ selectedMethod?.description || '保留当前采样值。' }}</span></div>
          <button class="head-btn" :disabled="saving" @click="saveAll">保存类别规则</button>
        </article>
      </div>
    </template>
    <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
    <p v-if="savedMessage" class="saved-message">{{ savedMessage }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getDataProcessing, saveDataProcessing } from '../api/dataProcessing'
import { createDashboardSocket } from '../socket/dashboardSocket'
import { SUBSYSTEMS } from '../config/subsystems'

const router = useRouter()
const subsystems = SUBSYSTEMS
const signals = ref([])
const categories = ref([])
const algorithms = ref([])
const snapshot = reactive({})
const categoryDraft = reactive({})
const categoryDraftSettings = reactive({})
const thresholdDraft = reactive({})
const activeTab = ref('signals')
const selectedCategory = ref('current')
const keyword = ref('')
const subsystemFilter = ref('')
const categoryFilter = ref('')
const statusFilter = ref('')
const page = ref(1)
const pageSize = 50
const connected = ref(false)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const savedMessage = ref('')
let socket = null
let refreshTimer = null
let requestInFlight = false

const categoryCounts = computed(() => Object.fromEntries(categories.value.map((category) => [category.id, signals.value.filter((signal) => effectiveCategory(signal) === category.id).length])))
const numericCount = computed(() => signals.value.filter((signal) => signal.dtype !== 'enum').length)
const discreteCount = computed(() => signals.value.filter((signal) => signal.dtype === 'enum').length)
const unconfiguredCount = computed(() => signals.value.filter((signal) => signal.status === '待配置阈值').length)
const activeCategory = computed(() => categories.value.find((item) => item.id === selectedCategory.value))
const selectedMethod = computed(() => algorithms.value.find((item) => item.id === categoryDraftSettings[selectedCategory.value]?.method))
const filteredSignals = computed(() => signals.value.filter((signal) => {
  const search = `${signal.id} ${signal.name} ${signal.subsystem}`.toLowerCase()
  return (!keyword.value || search.includes(keyword.value.toLowerCase()))
    && (!subsystemFilter.value || signal.subsystem_id === subsystemFilter.value)
    && (!categoryFilter.value || effectiveCategory(signal) === categoryFilter.value)
    && (!statusFilter.value || signal.status === statusFilter.value)
}))
const pageCount = computed(() => Math.max(1, Math.ceil(filteredSignals.value.length / pageSize)))
const pagedSignals = computed(() => filteredSignals.value.slice((page.value - 1) * pageSize, page.value * pageSize))

watch([keyword, subsystemFilter, categoryFilter, statusFilter], () => { page.value = 1 })
watch(pageCount, (count) => { if (page.value > count) page.value = count })

const methodWindow = (categoryId) => categoryDraftSettings[categoryId]?.window || 5
const methodsFor = (category) => algorithms.value.filter((method) => category.methods?.includes(method.id))
const effectiveCategory = (signal) => {
  const selected = categoryDraft[signal.id]
  return !selected || selected === 'auto' ? signal.auto_category : selected
}
const effectiveMethod = (signal) => categoryDraftSettings[effectiveCategory(signal)]?.method || signal.method
const effectiveMethodName = (signal) => algorithms.value.find((method) => method.id === effectiveMethod(signal))?.name || signal.method_name
const thresholdValue = (signal, key) => {
  const draft = thresholdDraft[signal.id]
  if (draft?.enabled === false) return ''
  if (draft && Object.prototype.hasOwnProperty.call(draft, key)) return draft[key] ?? ''
  return signal[`threshold_${key}`] ?? ''
}
const thresholdSource = (signal) => thresholdDraft[signal.id] ? '自定义阈值（待保存）' : signal.threshold_source
const statusClass = (severity) => severity === 'fault' ? 'danger' : severity === 'normal' ? 'ok' : 'pending'

function setSignalCategory(paramId, categoryId) {
  categoryDraft[paramId] = categoryId
  const signal = signals.value.find((item) => item.id === paramId)
  if (signal) {
    const selected = categories.value.find((item) => item.id === categoryId)
    signal.category = categoryId === 'auto' ? signal.auto_category : categoryId
    signal.category_name = categoryId === 'auto' ? categories.value.find((item) => item.id === signal.auto_category)?.name : selected?.name
  }
}

function editThreshold(signal, key, raw) {
  const existing = thresholdDraft[signal.id] || {
    minimum: signal.threshold_minimum ?? '',
    maximum: signal.threshold_maximum ?? ''
  }
  thresholdDraft[signal.id] = { minimum: existing.minimum, maximum: existing.maximum, [key]: raw }
}

function hydrate(data, preserveEdits = false) {
  signals.value = data.signals || []
  categories.value = data.categories || []
  algorithms.value = data.algorithms || []
  Object.assign(snapshot, {
    timestamp: data.timestamp,
    sequence: data.sequence,
    mode: data.mode,
    mode_label: data.mode_label,
    source_type: data.source_type
  })
  for (const category of categories.value) {
    const override = data.category_methods?.[category.id] || {}
    if (!preserveEdits || !categoryDraftSettings[category.id]) {
      categoryDraftSettings[category.id] = {
        method: override.method || category.default_method,
        window: override.window || data.settings?.window || 5,
        alpha: override.alpha || data.settings?.alpha || 0.3
      }
    }
  }
  if (!preserveEdits) {
    for (const signal of signals.value) categoryDraft[signal.id] = data.signal_categories?.[signal.id] || 'auto'
    for (const [paramId, threshold] of Object.entries(data.signal_thresholds || {})) {
      thresholdDraft[paramId] = threshold.enabled === false ? { enabled: false } : { ...threshold }
    }
  }
}

async function load({ initial = false, preserveEdits = false } = {}) {
  if (requestInFlight) return
  requestInFlight = true
  if (initial) loading.value = true
  try {
    const response = await getDataProcessing()
    if (response?.ok) {
      const data = response.data
      const edits = preserveEdits ? { ...categoryDraft } : null
      hydrate(data, preserveEdits)
      if (edits) Object.assign(categoryDraft, edits)
      if (!preserveEdits) error.value = ''
    }
  } catch (err) {
    error.value = err.response?.data?.error || '数据处理配置读取失败，请检查后端连接。'
  } finally {
    requestInFlight = false
    loading.value = false
  }
}

async function saveAll() {
  saving.value = true
  error.value = ''
  savedMessage.value = ''
  for (const category of categories.value) {
    const settings = categoryDraftSettings[category.id] || {}
    const windowSize = Number(settings.window)
    if (!Number.isInteger(windowSize) || windowSize < 1 || windowSize > 101) {
      error.value = `${category.name}的滤波窗口须为 1 到 101 之间的整数。`
      saving.value = false
      return
    }
    const alpha = Number(settings.alpha)
    if (!Number.isFinite(alpha) || alpha < 0.01 || alpha > 1) {
      error.value = `${category.name}的指数平滑系数须在 0.01 到 1 之间。`
      saving.value = false
      return
    }
  }
  try {
    const response = await saveDataProcessing({
      category_methods: Object.fromEntries(categories.value.map((category) => [category.id, { ...categoryDraftSettings[category.id] }])),
      signal_categories: Object.fromEntries(signals.value.map((signal) => [signal.id, categoryDraft[signal.id] || 'auto'])),
      signal_thresholds: { ...thresholdDraft }
    })
    if (!response?.ok) throw new Error(response?.error || '配置保存失败')
    savedMessage.value = '数据处理配置已保存。'
    await load({ preserveEdits: false })
  } catch (err) {
    error.value = err.response?.data?.error || err.message || '数据处理配置保存失败。'
  } finally {
    saving.value = false
  }
}

function clearError() {
  error.value = ''
}

onMounted(async () => {
  await load({ initial: true })
  socket = createDashboardSocket({
    onConnect: () => { connected.value = true },
    onDisconnect: () => { connected.value = false },
    onDashboardUpdate: () => {
      if (refreshTimer) window.clearTimeout(refreshTimer)
      refreshTimer = window.setTimeout(() => load({ preserveEdits: true }), 250)
    }
  })
})

onUnmounted(() => {
  if (refreshTimer) window.clearTimeout(refreshTimer)
  socket?.disconnect()
  socket = null
})
</script>

<style scoped>
.processing-screen{min-height:100vh;padding:18px;color:#d7f3ff;background:radial-gradient(circle at 18% 0%,rgba(48,146,255,.16),transparent 34%),linear-gradient(180deg,#04153d,#061b4a 56%,#04133a)}
.screen-header,.panel-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}
.screen-header{padding:18px 20px;border:1px solid rgba(88,203,255,.42);border-radius:12px;background:linear-gradient(180deg,rgba(8,36,90,.9),rgba(6,23,67,.92));box-shadow:inset 0 0 16px rgba(29,150,255,.14)}
.eyebrow{color:#86dfff;font-size:11px;letter-spacing:1.4px}.screen-header h1{margin:4px 0;color:#f2fbff;font-size:28px}.screen-header p,.panel-heading p,.category-editor>p{margin:5px 0 0;color:#94bfd9;font-size:13px}
.header-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.source-badge,.timestamp{color:#9ed5ee;font-size:12px}.source-badge.online{color:#65efb4}.head-btn,.pagination button{height:38px;padding:0 14px;border:1px solid rgba(108,216,255,.36);border-radius:8px;color:#e6fbff;background:linear-gradient(180deg,#1f5cad,#153f84);cursor:pointer}.head-btn.secondary{background:rgba(14,48,91,.8)}.head-btn:disabled{opacity:.55;cursor:wait}
.summary-grid{display:grid;grid-template-columns:repeat(4,minmax(120px,1fr));gap:10px;margin:12px 0}.summary-card,.panel{border:1px solid rgba(88,203,255,.28);border-radius:10px;background:linear-gradient(180deg,rgba(8,36,90,.78),rgba(6,23,67,.86));box-shadow:inset 0 0 14px rgba(29,150,255,.08)}.summary-card{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;color:#a9cde0;font-size:13px}.summary-card strong{color:#fff;font-size:22px}.summary-card .warn-text{color:#ffd365}
.view-tabs{display:flex;gap:6px;margin:12px 0}.view-tabs button{padding:10px 16px;border:1px solid rgba(88,203,255,.25);border-radius:8px;color:#a9cde0;background:rgba(8,30,73,.8);cursor:pointer}.view-tabs button.active{border-color:#4ac7ff;color:#effcff;background:#124477;box-shadow:0 0 12px rgba(50,181,255,.16)}
.filter-bar{display:flex;align-items:end;gap:10px;flex-wrap:wrap;margin-bottom:10px;padding:12px;border:1px solid rgba(88,203,255,.22);border-radius:9px;background:rgba(5,25,65,.74)}.filter-bar label,.form-field{display:grid;gap:5px;color:#9ac5dc;font-size:12px}.filter-bar input,.filter-bar select,.form-field input,.form-field select,.inline-select,.threshold-editor input{height:34px;padding:0 9px;border:1px solid rgba(75,170,226,.42);border-radius:6px;color:#dff7ff;background:#08234f;outline:none}.filter-bar input{width:200px}.filter-bar select{min-width:160px}.result-count{margin-left:auto;padding-bottom:8px;color:#87cfe9;font-size:12px}
.table-panel{overflow:hidden}.panel-heading{padding:14px 16px;border-bottom:1px solid rgba(88,203,255,.18)}.panel-heading h2,.category-list h2,.category-editor h2{margin:0;color:#effbff;font-size:17px}.timestamp{white-space:nowrap}.table-scroll{overflow:auto;max-height:calc(100vh - 340px);min-height:280px}table{width:100%;border-collapse:collapse;min-width:1120px}th{position:sticky;top:0;z-index:1;padding:11px 10px;color:#8ed8f2;background:#0a2a60;text-align:left;font-size:12px;font-weight:600}td{padding:9px 10px;border-bottom:1px solid rgba(99,170,214,.16);color:#d7f3ff;font-size:12px;vertical-align:middle}td strong{display:block;font-size:12px}td small{display:block;margin-top:3px;color:#83adc8;font-size:10px}.unit{display:inline!important;margin:0!important}.inline-select{min-width:142px;max-width:180px}.processed-value{color:#75efbd;font-weight:600}.threshold-editor{display:flex;align-items:center;gap:4px}.threshold-editor input{width:76px;height:30px}.threshold-editor span,.enum-threshold{color:#7faec9;font-size:11px}.status-pill{display:inline-block;padding:4px 8px;border-radius:20px;font-size:11px;white-space:nowrap}.status-pill.ok{color:#6df0b7;background:rgba(25,181,113,.15)}.status-pill.danger{color:#ff8891;background:rgba(238,73,86,.17)}.status-pill.pending{color:#ffd878;background:rgba(212,160,45,.14)}.empty-state{text-align:center;padding:32px;color:#91b8cf}.pagination{display:flex;align-items:center;justify-content:center;gap:12px;padding:10px;color:#96c6de;font-size:12px}.pagination button{height:30px;padding:0 12px;background:rgba(14,48,91,.8)}.pagination button:disabled{opacity:.4;cursor:default}
.category-layout{display:grid;grid-template-columns:minmax(210px,280px) 1fr;gap:12px}.category-list{padding:14px}.category-list h2{margin-bottom:10px}.category-list button{display:flex;width:100%;justify-content:space-between;align-items:center;margin-top:5px;padding:11px;border:1px solid transparent;border-radius:7px;color:#c4e7f8;background:rgba(8,31,75,.7);text-align:left;cursor:pointer}.category-list button.active{border-color:rgba(74,199,255,.6);background:rgba(18,68,119,.72)}.category-list small{color:#86b6d1}.category-editor{padding:22px}.category-editor h2{margin:5px 0 8px;font-size:21px}.form-field{margin-top:20px;max-width:430px}.form-field select,.form-field input{height:40px;font-size:14px}.form-field small{color:#83adc8}.form-columns{display:flex;gap:20px;flex-wrap:wrap}.rule-note{display:grid;gap:5px;margin:20px 0;padding:12px;border:1px solid rgba(88,203,255,.24);border-radius:7px;color:#a9d7ec;background:rgba(5,25,65,.72);font-size:12px}.rule-note strong{color:#dff7ff}.error-banner,.saved-message{margin:10px 0;padding:10px 12px;border-radius:7px;font-size:13px}.error-banner{color:#ffb4b8;background:rgba(190,55,65,.18)}.saved-message{color:#7bf0b9;background:rgba(30,155,100,.15)}
@media(max-width:900px){.screen-header,.panel-heading{align-items:flex-start;flex-direction:column}.summary-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.category-layout{grid-template-columns:1fr}.category-list{display:grid;grid-template-columns:repeat(2,1fr);gap:5px}.category-list h2{grid-column:1/-1}.result-count{margin-left:0}}
</style>
