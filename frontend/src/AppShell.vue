<template>
  <div class="shell app-shell">
    <aside class="module-sidebar">
      <div class="brand-block">
        <div class="brand-mark"><span>RH</span><i></i></div>
        <div class="brand-copy"><strong>RADAR HEALTH</strong><small>运行保障平台</small></div>
      </div>

      <div class="device-card">
        <span class="device-glyph">⌁</span>
        <div><small>监测设备</small><strong>天线系统</strong></div>
        <span class="device-state" :class="{ connected }" :title="connected ? '实时链路已连接' : '正在连接后端'"></span>
      </div>

      <nav class="module-navigation" aria-label="系统功能">
        <section v-for="group in navigation" :key="group.title" class="nav-group">
          <h2>{{ group.title }}</h2>
          <RouterLink v-for="item in group.items" :key="item.to" :to="item.to" class="nav-item" :class="{ active: routeMatches(item) }">
            <span class="nav-index">{{ item.index }}</span>
            <span class="nav-label">{{ item.label }}</span>
            <span v-if="item.to === '/alerts' && alertCount" class="nav-count">{{ alertCount }}</span>
            <span v-else-if="routeMatches(item)" class="nav-active-mark"></span>
          </RouterLink>
        </section>
      </nav>

      <div class="sidebar-footer">
        <span class="footer-led" :class="{ online: connected }"></span>
        <div><strong>{{ connected ? '数据链路在线' : '等待后端连接' }}</strong><small>{{ connected ? 'Socket.IO 实时更新' : '检查本机服务状态' }}</small></div>
        <span class="footer-version">V0.2</span>
      </div>
    </aside>

    <main class="workspace-column">
      <header class="system-bar">
        <div class="breadcrumb"><span>工作台</span><b>/</b><strong>{{ currentTitle }}</strong></div>
        <div class="system-readouts">
          <span class="readout"><i class="readout-led" :class="{ online: connected }"></i>{{ connected ? '实时通信正常' : '通信连接中' }}</span>
          <span class="readout readout-source"><span class="readout-separator"></span>{{ sourceLabel }}</span>
          <span class="readout clock-readout">{{ clockLabel }}</span>
        </div>
      </header>
      <section class="workspace-content">
        <RouterView />
      </section>
    </main>

    <nav class="quick-rail" aria-label="快捷操作">
      <span class="rail-caption">快捷<br />入口</span>
      <button v-for="item in quickActions" :key="item.label" type="button" :title="item.label" :aria-label="item.label" @click="router.push(item.to)">
        <span>{{ item.glyph }}</span>
      </button>
      <div class="rail-bottom"><span class="rail-line"></span><span>LOCAL</span></div>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { createDashboardSocket } from './socket/dashboardSocket'

const route = useRoute()
const router = useRouter()
const connected = ref(false)
const latestPayload = ref(null)
const now = ref(new Date())
let socket
let clockTimer

const navigation = [
  { title: '运行监控', items: [
    { index: '01', label: '健康总览', to: '/health' },
    { index: '02', label: '运行状态', to: '/status-monitor' },
    { index: '03', label: '实时告警', to: '/alerts' },
    { index: '04', label: '子系统台账', to: '/subsystem/azimuth-motor-1' }
  ] },
  { title: '数据与诊断', items: [
    { index: '05', label: '数据处理', to: '/data-processing' },
    { index: '06', label: '分层故障诊断', to: '/fault-diagnosis' },
    { index: '06A', label: '轴承部件诊断', to: '/bearing-diagnosis' },
    { index: '07', label: '诊断记录', to: '/fault-history' },
    { index: '08', label: '诊断查询', to: '/diagnosis-query' },
    { index: '09', label: '健康算法', to: '/health-algorithm' },
    { index: '10', label: '雷达重构', to: '/radar-reconstruction' }
  ] },
  { title: '档案与维护', items: [
    { index: '11', label: '健康历史', to: '/health-history' },
    { index: '12', label: '健康数据库', to: '/health-database' },
    { index: '13', label: '故障知识库', to: '/fault-database' },
    { index: '14', label: '系统自检', to: '/system-self-check' },
    { index: '15', label: '用户管理', to: '/user-management' },
    { index: '16', label: '系统扩展', to: '/system-extension' },
    { index: '17', label: '接口配置', to: '/demo/ip' }
  ] }
]

const quickActions = [
  { label: '打开分层故障诊断', glyph: '⌕', to: '/fault-diagnosis' },
  { label: '打开数据处理配置', glyph: '≋', to: '/data-processing' },
  { label: '打开健康算法', glyph: '◌', to: '/health-algorithm' },
  { label: '打开系统自检', glyph: '✓', to: '/system-self-check' }
]

const titleMap = {
  health: '健康总览', 'health-history': '健康历史', 'health-database': '健康数据库',
  'fault-database': '故障知识库', alerts: '实时告警', 'health-algorithm': '健康算法',
  'radar-reconstruction': '雷达重构', 'data-processing': '数据处理',
  'fault-diagnosis': '分层故障诊断', 'bearing-diagnosis': '轴承部件诊断', 'fault-history': '诊断记录',
  'system-self-check': '系统自检', 'status-monitor': '运行状态',
  'user-management': '用户管理', 'diagnosis-query': '诊断查询',
  'system-extension': '系统扩展', 'subsystem-detail': '子系统台账',
  'demo-monitor': '接口监视', 'demo-send': '报文发送', 'demo-ip': '接口配置',
  'demo-health-dashboard': '健康演示', 'demo-fault-history': '故障演示'
}
const currentTitle = computed(() => titleMap[route.name] || '系统工作台')
const alertCount = computed(() => Number(latestPayload.value?.data?.alerts?.active_count || 0))
const sourceLabel = computed(() => {
  const modeLabel = latestPayload.value?.scenario_record?.mode_label
  return modeLabel ? `数据源 · ${modeLabel}` : '数据源 · 等待快照'
})
const clockLabel = computed(() => now.value.toLocaleString('zh-CN', { hour12: false }))

function routeMatches(item) {
  if (item.to.startsWith('/subsystem/')) return route.path.startsWith('/subsystem/')
  return route.path === item.to || (item.to === '/demo/ip' && route.name === 'demo-ip')
}

onMounted(() => {
  clockTimer = window.setInterval(() => { now.value = new Date() }, 1000)
  socket = createDashboardSocket({
    onConnect: () => { connected.value = true },
    onDisconnect: () => { connected.value = false },
    onDashboardUpdate: (payload) => { latestPayload.value = payload }
  })
})

onUnmounted(() => {
  if (clockTimer) window.clearInterval(clockTimer)
  socket?.disconnect()
})
</script>
