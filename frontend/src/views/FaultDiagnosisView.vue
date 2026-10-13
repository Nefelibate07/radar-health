<template>
  <section class="diagnosis-screen">
    <header class="screen-header">
      <div><span class="eyebrow">HIERARCHICAL FAULT DIAGNOSIS</span><h1>分层故障诊断</h1><p>独立于健康度评估，逐级显示整机、子系统、功能部件的分类范围与实时诊断结果。</p></div>
      <div class="header-actions"><span class="source-badge" :class="connected ? 'online' : ''">{{ connected ? '实时数据已连接' : '连接中' }} · {{ data.mode_label || '等待快照' }}</span><button class="head-btn secondary" @click="router.push('/data-processing')">配置数据处理</button><button class="head-btn secondary" @click="router.push('/health')">返回主界面</button></div>
    </header>

    <div v-if="data.system" class="system-card" :class="statusClass(data.system.status)">
      <div class="system-copy"><span class="level-label">整机实时诊断</span><h2>{{ data.system.fault_class || data.system.status }}</h2><p>{{ data.system.status === '故障' ? `主要故障位置：${data.system.primary_subsystem} · ${data.system.primary_component || '部件待确认'}` : data.system.status === '待完善' ? '存在尚未配置阈值或无法判别的数值测点。' : '当前可判定测点未发现故障。' }}</p>
        <div class="taxonomy-block system-taxonomy"><span class="taxonomy-title">整机级分类范围</span><div class="taxonomy-tags"><span v-for="item in data.system.candidate_fault_classes || []" :key="item" class="taxonomy-tag">{{ item }}</span></div></div>
      </div>
      <div class="system-metrics"><div><strong>{{ data.summary?.fault_subsystem_count ?? 0 }}</strong><span>故障子系统</span></div><div><strong>{{ data.summary?.fault_component_count ?? 0 }}</strong><span>故障部件</span></div><div><strong>{{ data.summary?.fault_signal_count ?? 0 }}</strong><span>故障测点</span></div><div><strong>{{ data.summary?.unconfigured_numeric_count ?? 0 }}</strong><span>待配阈值</span></div></div>
    </div>

    <div class="filter-bar"><label>子系统<select v-model="subsystemFilter"><option value="">全部 {{ data.summary?.subsystem_count ?? 0 }} 个子系统</option><option v-for="item in data.subsystems || []" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><label>诊断状态<select v-model="statusFilter"><option value="">全部</option><option>故障</option><option>待完善</option><option>无数据</option><option>正常</option></select></label><span class="snapshot-meta">分类覆盖 {{ data.summary?.categorized_subsystem_count ?? 0 }}/{{ data.summary?.subsystem_count ?? 0 }} 子系统 · {{ data.summary?.categorized_component_count ?? 0 }}/{{ data.summary?.component_count ?? 0 }} 部件 · {{ data.summary?.signal_count ?? 0 }} 测点 · 快照 {{ data.timestamp || '--' }} · #{{ data.sequence ?? '--' }}</span></div>

    <div class="hierarchy-grid">
      <article v-for="subsystem in visibleSubsystems" :key="subsystem.id" class="subsystem-card" :class="statusClass(subsystem.status)">
        <header class="subsystem-header"><div><span class="level-label">子系统</span><h2>{{ subsystem.name }}</h2><small>{{ subsystem.signal_count ? `${subsystem.evaluated_signal_count} / ${subsystem.signal_count} 个测点已判别` : '暂无接入测点' }}</small></div><div class="subsystem-state"><span class="status-pill" :class="statusClass(subsystem.status)">{{ subsystem.status }}</span><strong v-if="subsystem.fault_class">当前：{{ subsystem.fault_class }}</strong><small v-else class="no-current-class">当前未检出明确分类</small></div></header>
        <div class="taxonomy-block subsystem-taxonomy"><span class="taxonomy-title">子系统级故障分类</span><div class="taxonomy-tags"><span v-for="item in subsystem.candidate_fault_classes || []" :key="item" class="taxonomy-tag">{{ item }}</span><span v-if="!subsystem.candidate_fault_classes?.length" class="taxonomy-empty">分类待配置</span></div></div>
        <div class="component-list">
          <details v-for="component in subsystem.components" :key="component.id" class="component-card" :open="component.status === '故障'">
            <summary class="component-summary-row"><span class="component-summary-main"><span class="component-name"><small>功能部件 / 测点组</small><strong>{{ component.name }}</strong></span><span class="component-meta">{{ component.signal_count }} 个测点<span v-if="component.data_scope"> · {{ component.data_scope }}</span></span><span class="taxonomy-title component-taxonomy-title">部件级故障分类</span><span class="taxonomy-tags component-taxonomy-tags"><span v-for="item in component.candidate_fault_classes || []" :key="item" class="taxonomy-tag">{{ item }}</span><span v-if="!component.candidate_fault_classes?.length" class="taxonomy-empty">分类待配置</span></span></span><span class="component-state"><em v-if="component.fault_class" class="active-class">当前：{{ component.fault_class }}</em><i class="status-pill" :class="statusClass(component.status)">{{ component.status }}</i></span></summary>
            <div class="component-content">
              <p v-if="component.data_scope" class="empty-component">{{ component.data_scope }}；以下类别暂作范围参考，不代表实时判定。</p>
              <div v-if="component.signals.length" class="signal-table"><div class="signal-head"><span>数据</span><span>当前值 / 处理值</span><span>判据</span><span>状态</span></div>
              <div v-for="signal in component.signals" :key="signal.id" class="signal-row"><span>{{ signal.name }}<small>{{ signal.id }}</small></span><span>{{ signal.current_display }} / {{ signal.processed_display }} {{ signal.unit }}</span><span>{{ signal.fault_class ? `${signal.fault_class} · ` : '' }}{{ signal.reason }}</span><span :class="statusClass(signal.severity === 'fault' ? '故障' : signal.severity === 'normal' ? '正常' : '待完善')">{{ signal.status }}</span></div>
              </div>
              <p v-if="!component.faults.length && component.status === '待完善'" class="pending-note">该部件含有尚未配置阈值的数值量；可在数据处理页补充范围。</p>
            </div>
          </details>
        </div>
      </article>
    </div>
    <footer class="method-note">{{ data.classification_note || '分类由配置阈值和枚举规则驱动。' }} <span>更新时间：{{ data.timestamp || '--' }}</span></footer>
    <p v-if="error" class="error-banner">{{ error }}</p>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getFaultDiagnosis } from '../api/dataProcessing'
import { createDashboardSocket } from '../socket/dashboardSocket'

const router = useRouter()
const data = ref({})
const connected = ref(false)
const error = ref('')
const subsystemFilter = ref('')
const statusFilter = ref('')
let socket = null
let refreshTimer = null
let requestInFlight = false

const visibleSubsystems = computed(() => (data.value.subsystems || []).filter((item) => (!subsystemFilter.value || item.id === subsystemFilter.value) && (!statusFilter.value || item.status === statusFilter.value)))
const statusClass = (status) => status === '故障' ? 'danger' : status === '正常' ? 'ok' : status === '无数据' ? 'no-data' : 'pending'

async function load() {
  if (requestInFlight) return
  requestInFlight = true
  try {
    const response = await getFaultDiagnosis()
    if (response?.ok) {
      data.value = response.data
      error.value = ''
    }
  } catch (err) {
    error.value = err.response?.data?.error || '分层诊断读取失败，请检查后端服务。'
  } finally {
    requestInFlight = false
  }
}

onMounted(async () => {
  await load()
  socket = createDashboardSocket({
    onConnect: () => { connected.value = true },
    onDisconnect: () => { connected.value = false },
    onDashboardUpdate: () => {
      if (refreshTimer) window.clearTimeout(refreshTimer)
      refreshTimer = window.setTimeout(load, 220)
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
.diagnosis-screen{min-height:100vh;padding:18px;color:#d7f3ff;background:radial-gradient(circle at 18% 0%,rgba(48,146,255,.16),transparent 34%),linear-gradient(180deg,#04153d,#061b4a 56%,#04133a)}.screen-header{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:18px 20px;border:1px solid rgba(88,203,255,.42);border-radius:12px;background:linear-gradient(180deg,rgba(8,36,90,.9),rgba(6,23,67,.92))}.eyebrow{color:#86dfff;font-size:11px;letter-spacing:1.4px}.screen-header h1{margin:4px 0;color:#f2fbff;font-size:28px}.screen-header p{margin:5px 0 0;color:#94bfd9;font-size:13px}.header-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap}.source-badge,.snapshot-meta{color:#9ed5ee;font-size:12px}.source-badge.online{color:#65efb4}.head-btn{height:38px;padding:0 14px;border:1px solid rgba(108,216,255,.36);border-radius:8px;color:#e6fbff;background:linear-gradient(180deg,#1f5cad,#153f84);cursor:pointer}.head-btn.secondary{background:rgba(14,48,91,.8)}
.system-card,.subsystem-card{border:1px solid rgba(88,203,255,.28);border-radius:10px;background:linear-gradient(180deg,rgba(8,36,90,.78),rgba(6,23,67,.86));box-shadow:inset 0 0 14px rgba(29,150,255,.08)}.system-card{display:flex;align-items:center;justify-content:space-between;gap:18px;margin:12px 0;padding:16px 20px;border-left:4px solid #ffd365}.system-card.danger{border-left-color:#ff6674}.system-card.ok{border-left-color:#4be7a5}.system-card h2{margin:3px 0;color:#fff;font-size:21px}.system-card p{margin:6px 0 0;color:#9fc7dc;font-size:12px}.level-label{color:#87cfe9;font-size:11px}.system-metrics{display:flex;gap:20px}.system-metrics div{display:grid;justify-items:center;gap:3px;min-width:74px}.system-metrics strong{color:#fff;font-size:22px}.system-metrics span{color:#8bb4cb;font-size:10px}
.filter-bar{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin:12px 0;padding:12px;border:1px solid rgba(88,203,255,.22);border-radius:9px;background:rgba(5,25,65,.74)}.filter-bar label{display:grid;gap:5px;color:#9ac5dc;font-size:12px}.filter-bar select{height:34px;min-width:180px;padding:0 9px;border:1px solid rgba(75,170,226,.42);border-radius:6px;color:#dff7ff;background:#08234f}.snapshot-meta{margin-left:auto;padding-bottom:8px}.hierarchy-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.subsystem-card{overflow:hidden}.subsystem-header{display:flex;justify-content:space-between;gap:12px;padding:13px 14px;border-bottom:1px solid rgba(88,203,255,.16)}.subsystem-header h2{margin:3px 0;color:#ecfaff;font-size:15px}.subsystem-header small{color:#83adc8;font-size:10px}.subsystem-state{display:grid;justify-items:end;align-content:start;gap:5px}.subsystem-state strong{color:#ffc77a;font-size:11px}.status-pill{display:inline-block;padding:4px 8px;border-radius:20px;font-size:10px;white-space:nowrap;font-style:normal}.status-pill.ok{color:#6df0b7;background:rgba(25,181,113,.15)}.status-pill.danger{color:#ff8891;background:rgba(238,73,86,.17)}.status-pill.pending{color:#ffd878;background:rgba(212,160,45,.14)}.subsystem-candidates{margin:9px 12px 4px;padding:8px 9px;border:1px solid rgba(99,170,214,.18);border-radius:6px;background:rgba(4,23,58,.5);line-height:1.7}.candidate-note{margin:2px 12px 7px;color:#83adc8;font-size:9px;line-height:1.5}.component-list{display:grid;gap:5px;padding:9px}.component-card{border:1px solid rgba(99,170,214,.16);border-radius:7px;background:rgba(4,23,58,.5)}.component-card summary{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:9px 10px;cursor:pointer;list-style:none}.component-card summary::-webkit-details-marker{display:none}.component-card summary>span:first-child{display:grid;gap:2px}.component-card summary small,.candidate-line span{color:#77b9d8;font-size:10px}.component-card summary strong{color:#d8f4ff;font-size:12px}.component-summary{display:flex;align-items:center;gap:7px}.component-summary em{color:#ffd17a;font-size:10px;font-style:normal}.component-summary b{color:#7faec9;font-size:9px;font-weight:400}.component-content{padding:0 10px 10px}.candidate-line{margin:4px 0 8px;color:#9ebdd0;font-size:10px}.candidate-line span{margin-right:8px}.signal-table{overflow:auto}.signal-head,.signal-row{display:grid;grid-template-columns:1.15fr 1fr 1.3fr .6fr;gap:8px;min-width:580px;padding:6px;border-bottom:1px solid rgba(99,170,214,.12);font-size:10px}.signal-head{color:#82cde8}.signal-row{color:#c4e1ef}.signal-row small{display:block;margin-top:2px;color:#769db6;font-size:9px}.signal-row .ok{color:#6df0b7}.signal-row .danger{color:#ff8891}.signal-row .pending{color:#ffd878}.pending-note{margin:7px 0 0;color:#ffd878;font-size:10px}.method-note{display:flex;justify-content:space-between;gap:12px;margin-top:12px;padding:10px 12px;border:1px solid rgba(88,203,255,.2);border-radius:8px;color:#8bb6cc;background:rgba(5,25,65,.7);font-size:11px;line-height:1.5}.method-note span{white-space:nowrap}.error-banner{margin:10px 0;padding:10px 12px;border-radius:7px;color:#ffb4b8;background:rgba(190,55,65,.18);font-size:13px}
@media(max-width:1000px){.hierarchy-grid{grid-template-columns:1fr}.system-card{align-items:flex-start;flex-direction:column}.screen-header{align-items:flex-start;flex-direction:column}.snapshot-meta{margin-left:0}.method-note{flex-direction:column}.method-note span{white-space:normal}}

.system-copy{flex:1;min-width:0}.system-taxonomy{margin-top:10px}.taxonomy-block{padding:9px 11px;border:1px solid rgba(88,203,255,.17);border-radius:7px;background:rgba(4,23,58,.42)}.subsystem-taxonomy{margin:9px 12px 2px}.taxonomy-title{display:block;margin-bottom:6px;color:#83cde8;font-size:10px;font-weight:700;letter-spacing:.3px}.taxonomy-tags{display:flex;flex-wrap:wrap;gap:5px}.taxonomy-tag{display:inline-flex;align-items:center;padding:4px 7px;border:1px solid rgba(107,215,255,.17);border-radius:12px;color:#c3e8f6;background:rgba(30,101,148,.18);font-size:10px;line-height:1.35}.taxonomy-empty{color:#ffd878;font-size:10px}.component-summary-row{align-items:flex-start!important}.component-summary-main{display:grid!important;gap:5px;min-width:0;flex:1}.component-name{display:grid;gap:2px}.component-meta{color:#86aec4;font-size:9px;line-height:1.4}.component-taxonomy-title{margin:2px 0 0}.component-taxonomy-tags{max-width:100%}.component-state{display:grid;justify-items:end;gap:6px;flex:none}.active-class{max-width:180px;color:#ffd17a;font-size:10px;font-style:normal;text-align:right;white-space:normal}.no-current-class{color:#83adc8;text-align:right}.empty-component{margin:7px 0;color:#ffd878;font-size:10px;line-height:1.5}.status-pill.no-data{color:#9ab5c8;background:rgba(102,132,153,.15)}
@media(max-width:680px){.system-metrics{width:100%;justify-content:space-between;gap:6px;flex-wrap:wrap}.system-metrics div{min-width:62px}.subsystem-header{align-items:flex-start}.component-summary-row{gap:7px!important}.component-state{max-width:95px}.active-class{max-width:95px}.taxonomy-tag{font-size:9px;padding:3px 6px}}
</style>
