<template>
  <section class="health-screen">
    <button
      v-if="hasActiveAlarm"
      class="corner-alarm"
      :class="[`severity-${alarmSeverity}`]"
      type="button"
      @click="goAlertsPage"
      :title="alarmBannerText"
    >
      <span class="corner-alarm-icon">{{ alarmBannerIcon }}</span>
      <span class="corner-alarm-text">{{ alarmBannerText }}</span>
    </button>

    <header class="screen-header panel-box">
      <div class="header-nav">
        <button
          v-for="item in topLeftTabs"
          :key="item.label"
          class="tab-chip"
          type="button"
          @click="handleTopTabClick(item)"
        >
          {{ item.label }}
        </button>
      </div>
      <h1 class="screen-title">天线系统健康监测</h1>
      <div class="header-nav header-nav-right">
        <button
          v-for="item in topRightTabs"
          :key="item.label"
          class="tab-chip"
          type="button"
          @click="handleTopTabClick(item)"
        >
          {{ item.label }}
        </button>
      </div>
    </header>

    <div class="screen-main">
      <aside class="left-col">
        <article class="panel-box info-card">
          <h2 class="card-title">设备基本信息</h2>
          <div class="meta-row">
            <span>设备: {{ deviceLabel }}</span>
            <span>时间: {{ displayTimestamp }}</span>
          </div>

          <!-- 大号健康分数突出显示 -->
          <div class="health-score-hero" :class="`health-level-${getHealthLevel()}`">
            <div class="score-number">{{ leftHealthScore }}</div>
            <div class="score-label">系统健康度</div>
            <div class="score-status" :class="`status-${getHealthLevel()}`">
              {{ systemStatusText }}
            </div>
          </div>

          <!-- 其他统计信息次要显示 -->
          <div class="stats-grid-secondary">
            <div class="stat-item">
              <p class="label">运行时长</p>
              <p class="value accent-cyan">{{ runtimeLabel }}</p>
            </div>
            <div class="stat-item">
              <p class="label">异常次数</p>
              <p class="value accent-yellow">{{ leftAbnormalCount }}</p>
            </div>
          </div>
        </article>

        <article class="panel-box list-card">
          <h2 class="card-title">电机运行状态监测</h2>
          <div class="row-head">
            <span>测点名称</span>
            <span>数据时间</span>
            <span>电流</span>
            <span>状态</span>
          </div>
          <!-- 自动滚动容器 -->
          <div class="auto-scroll-container">
            <div v-for="(item, idx) in leftMotors" :key="item.name + '_' + idx" class="row-item" :style="{ animationDelay: `${idx * 0.5}s` }">
              <span>{{ item.name }}</span>
              <span>{{ item.time }}</span>
              <span>{{ item.current }}</span>
              <span class="accent-cyan">{{ item.status }}</span>
            </div>
          </div>
        </article>
      </aside>

      <main class="center-col">
        <article class="panel-box hero-card">
          <div class="hero-top">
            <div class="hero-tabs">
              <button
                class="hero-tab-btn"
                :class="{ active: heroTab === 'ring' }"
                type="button"
                @click="heroTab = 'ring'"
              >
                环形总览
              </button>
              <button
                class="hero-tab-btn"
                :class="{ active: heroTab === 'graph' }"
                type="button"
                @click="heroTab = 'graph'"
              >
                关系图
              </button>
            </div>
            <span>{{ heroTitle }}</span>
            <div class="hero-actions">
              <label class="graph-import-btn" :class="{ disabled: graphImporting }" title="导入 VSDX 或 Excel 关系图">
                {{ graphImporting ? '解析中…' : '导入关系图' }}
                <input
                  ref="graphFileInput"
                  type="file"
                  accept=".vsdx,.xlsx,.xls,.csv"
                  :disabled="graphImporting"
                  @change="handleGraphFileChange"
                />
              </label>
              <button v-if="graphIsImported" class="graph-reset-btn" type="button" @click="resetImportedGraph">
                内置关系
              </button>
              <span class="source-badge">合成演示快照 · 唯一信号源</span>
            </div>
          </div>
          <div class="scenario-toolbar" role="group" aria-label="场景模拟切换">
            <span class="scenario-toolbar-label">场景模拟</span>
            <button
              v-for="item in scenarioModes"
              :key="item.key"
              class="scenario-btn"
              :class="[
                `scenario-btn-${item.tone}`,
                { active: activeScenarioMode === item.key }
              ]"
              type="button"
              :disabled="scenarioSwitching"
              :title="`快捷键 ${item.shortcut}：${item.label}`"
              @click="selectScenarioMode(item.key)"
            >
              <span class="scenario-key">{{ item.shortcut }}</span>
              <span>{{ item.shortLabel }}</span>
            </button>
            <span class="scenario-shortcut-note">键盘 0–5 同样可用</span>
          </div>
          <div class="hero-body">
            <!-- 演示子系统摆进7x5对称网格，正中心那一格固定放雷达图片；子系统数量不足以
                 填满剩余格子时，多出来的格子渲染成空占位格(is-empty)，保证网格本身始终
                 对称、中心区域始终被图片完整填满 -->
            <div v-if="heroTab === 'ring'" class="ring-stage">
              <div
                v-for="(cell, idx) in ringGridCells"
                :key="idx"
                class="ring-cell"
                :class="{ 'ring-cell--empty': cell.type === 'empty' }"
              >
                <img v-if="cell.type === 'image'" :src="leidaImg" alt="雷达天线" class="ring-center-image" />
                <div
                  v-else-if="cell.type === 'subsystem'"
                  class="ring-card"
                  :class="[cell.data.statusClass, { 'is-disabled': !cell.data.mapped_subsystem_id && !cell.data.primary_parameter }]"
                  @click="goGraphNode(cell.data)"
                >
                  <h3 :title="cell.data.name">{{ cell.data.name }}</h3>
                  <strong>{{ cell.data.displayHealth }}%</strong>
                </div>
                <div v-else class="ring-fill" :class="cell.statusClass" aria-hidden="true"></div>
              </div>
            </div>

            <!-- 子系统关系图：监控计算机在最左列，下级从左到右按层分列排布；箭头由下级指向上级，
                 指向同一个上级的箭头统一用同一种颜色，指向不同上级的箭头颜色不同，靠颜色就能看出
                 一条线具体指向谁，不用再去数箭头连的是哪一张卡片 -->
            <div v-else ref="graphStageRef" class="graph-stage">
              <svg class="graph-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
                <defs>
                  <marker
                    v-for="(color, key) in STATUS_EDGE_COLORS"
                    :id="`graph-arrow-${key}`"
                    :key="key"
                    markerWidth="2.6"
                    markerHeight="2.6"
                    refX="2.2"
                    refY="1.3"
                    orient="auto"
                    markerUnits="userSpaceOnUse"
                  >
                    <path d="M0,0 L2.4,1.3 L0,2.6 Z" :fill="color" />
                  </marker>
                </defs>
                <path
                  v-for="(e, idx) in graphEdgeLines"
                  :key="idx"
                  :d="e.curve"
                  class="graph-edge"
                  :class="{ 'graph-edge-same-column': e.sameColumn }"
                  :style="{ stroke: e.color }"
                  :marker-end="`url(#graph-arrow-${e.statusKey})`"
                />
              </svg>
              <div class="graph-hub-node" :style="graphHubStyle">
                <span>{{ graphRootLabel }}</span>
              </div>
              <div
                v-for="s in graphNodes"
                :key="s.id"
                class="graph-card"
                :class="[s.statusClass, { 'is-disabled': !s.mapped_subsystem_id && !s.primary_parameter }]"
                :style="s.graphStyle"
                @click="goGraphNode(s)"
              >
                <h3 :title="s.name">{{ s.name }}</h3>
                <strong>{{ s.displayHealth }}%</strong>
              </div>
            </div>
          </div>
          <p class="hero-caption">
            {{ graphIsImported ? `导入关系图 ${graphNodeCount} 个节点` : `全系统 ${subsystemsWithSim.length} 子系统` }} · {{ totalParamCount }} 监测参数
            <span class="scenario-hint" :title="scenarioShortcutTitle">{{ scenarioLabel }}</span>
            <span v-if="authorityReplayActive" class="authority-replay-hint" :title="authorityReplayTitle">合成演示快照</span>
            <span v-if="graphImportMessage" class="graph-import-message">{{ graphImportMessage }}</span>
          </p>
        </article>

        <div class="bottom-grid">
          <article class="panel-box table-card log-entry" @click="goAlertsPage" title="Open fault history">
            <h2 class="card-title">设备故障日志</h2>
            <div class="row-head">
              <span>状态</span>
              <span>故障等级</span>
              <span>故障时间</span>
              <span>故障部位</span>
              <span>持续</span>
            </div>
            <!-- 故障日志滚动容器 -->
            <div class="auto-scroll-container log-scroll">
              <div v-for="(item, i) in faults" :key="'fault_' + i" class="row-item" :style="{ animationDelay: `${i * 0.8}s` }">
                <span>{{ item.status }}</span>
                <span>{{ item.level }}</span>
                <span>{{ item.time }}</span>
                <span>{{ item.part }}</span>
                <span>{{ item.duration }}</span>
              </div>
              <!-- 如果故障数不足，重复显示以保证滚动效果 -->
              <div v-if="faults.length < 3" v-for="(item, i) in faults" :key="'fault_repeat_' + i" class="row-item" :style="{ animationDelay: `${(faults.length + i) * 0.8}s` }">
                <span>{{ item.status }}</span>
                <span>{{ item.level }}</span>
                <span>{{ item.time }}</span>
                <span>{{ item.part }}</span>
                <span>{{ item.duration }}</span>
              </div>
            </div>
          </article>

          <article class="panel-box trend-card trend-entry" @click="goAlertsTrendPage" title="Open health alerts">
            <h2 class="card-title">设备健康趋势</h2>
            <div class="trend-wrap">
              <svg viewBox="0 0 680 260" preserveAspectRatio="none" class="trend-svg">
                <g class="grid-lines">
                  <line v-for="y in [40, 80, 120, 160, 200]" :key="`g-${y}`" x1="60" :y1="y" x2="650" :y2="y" />
                </g>
                <line class="axis" x1="60" y1="220" x2="650" y2="220" />
                <line class="axis" x1="60" y1="20" x2="60" y2="220" />
                <polyline v-if="trendScorePolyline" class="score-line" :points="trendScorePolyline" />
                <polyline v-if="trendFaultPolyline" class="fault-line" :points="trendFaultPolyline" />
                <g v-for="(p, idx) in trendPlotPoints" :key="`trend-${idx}`">
                  <circle class="score-dot" :cx="p.x" :cy="p.yScore" r="4" />
                  <circle class="fault-dot" :cx="p.x" :cy="p.yFault" r="3.5" />
                  <text class="score-label" :x="p.x" :y="p.yScore - 10">{{ p.score }}</text>
                  <text class="fault-label" :x="p.x" :y="p.yFault + 16">{{ p.fault_count }}</text>
                  <text class="x-label" :x="p.x" y="242">{{ shortDate(p.display_date || p.date) }}</text>
                </g>
              </svg>
            </div>
          </article>
        </div>
      </main>

      <aside class="right-col">
        <article class="panel-box telemetry-card">
          <div class="telemetry-header">
            <h2 class="card-title">天线反馈</h2>
            <button class="param-selector-btn" @click="showParamSelector = !showParamSelector">
              ⚙ 选择
            </button>
          </div>

          <!-- 参数选择模态框 -->
          <div v-if="showParamSelector" class="param-selector-modal">
            <div class="modal-header">
              <span>选择显示参数（可多选）</span>
              <button @click="showParamSelector = false">✕</button>
            </div>
            <div class="param-list-container">
              <div class="param-item" v-for="param in allParameters" :key="param.id" @click="toggleParam(param.id)">
                <input type="checkbox" :checked="selectedParams.has(param.id)" @click.stop="toggleParam(param.id)" />
                <span class="param-name">{{ param.subsystem }}-{{ param.name }}</span>
              </div>
            </div>
            <div class="modal-footer">
              <button @click="showParamSelector = false" class="close-btn">确定</button>
            </div>
          </div>

          <!-- 显示已选参数 -->
          <div class="telemetry-display">
            <div class="row-head">
              <span>测点名称</span>
              <span>数据信息</span>
              <span>操作</span>
            </div>
            <div class="telemetry-rows-scroll">
              <div v-for="item in selectedFeedback" :key="item.id" class="row-item telemetry-row">
                <span class="param-label">{{ item.fullName }}</span>
                <div class="data-section">
                  <div class="data-value">{{ item.value }}</div>
                  <div class="data-time">{{ item.time }}</div>
                </div>
                <button class="delete-btn" @click="removeParam(item.id)">删除</button>
              </div>
            </div>
          </div>
        </article>

        <article class="panel-box alarm-card alarm-entry" @click="goAlertsPage">
          <h2 class="card-title">报警信息</h2>
          <div class="alarm-row"><span>描述</span><p>{{ alarmInfo.description }}</p></div>
          <div class="alarm-row"><span>现象</span><p>{{ alarmInfo.phenomenon }}</p></div>
          <div class="alarm-row"><span>原因</span><p>{{ alarmInfo.cause }}</p></div>
        </article>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { createDashboardSocket } from '../socket/dashboardSocket'
import { API_PREFIX } from '../config/backend'
import leidaImage from '../../asserts/leida.svg'
import { SUBSYSTEMS, getSubsystemStatusClass, getSubsystemStatusText } from '../config/subsystems'
import { EDGES as GRAPH_EDGES, ROOT_ID as GRAPH_ROOT_ID } from '../config/subsystemRelationships'
import { buildColumnLayout, buildRelationshipPath } from '../utils/graphColumnLayout'
import { scoreToStatus, scoreToClass } from '../utils/healthStatus'

// 关系图连线颜色只代表健康状态(绿/黄/红)，不用来区分子系统——排障场景只关心"坏没坏、
// 坏在哪"，一眼全绿就该能直接跳过这个界面，用一堆颜色区分子系统反而增加视觉噪音。
// 复用节点卡片本来就有的三色状态语义(.ring-card/.graph-card 的 status-ok/warn/danger)，
// 保持全站配色一致。
const STATUS_EDGE_COLORS = {
  ok: '#44f2a6',
  warn: '#ffd365',
  danger: '#ff5b6b'
}
const statusKeyFromClass = (cls) => {
  if (cls === 'status-warn') return 'warn'
  if (cls === 'status-danger') return 'danger'
  return 'ok'
}

const router = useRouter()
const leidaImg = leidaImage

const topLeftTabs = [
  { label: '数据处理', route: '/data-processing' },
  { label: 'IP设置', route: '/demo/ip' },
  { label: '算法管理', route: '/health-algorithm' },
  { label: '时序健康', route: '/radar-reconstruction' },
  { label: '系统自检', route: '/system-self-check' },
  { label: '状态监测', route: '/status-monitor' },
  { label: '健康评估', route: '/alerts' }
]

const topRightTabs = [
  { label: '分层故障诊断', route: '/fault-diagnosis' },
  { label: '用户管理', route: '/user-management' },
  { label: '健康数据库', route: '/health-database' },
  { label: '故障数据库', route: '/fault-database' },
  { label: '诊断查询', route: '/diagnosis-query' },
  { label: '系统扩展', route: '/system-extension' }
]

const handleTopTabClick = (item) => {
  if (item.route) {
    router.push(item.route)
  }
}

const goAlertsPage = () => {
  router.push('/fault-history')
}
const goAlertsTrendPage = () => {
  router.push('/alerts')
}

const dashboardPayload = ref(null)
const lastUpdated = ref('')
let dashboardSocket = null
const faultPreviewRows = ref([])
const dailyScores = ref([])

const clamp = (value, min = 0, max = 100) => {
  const n = Number(value)
  if (!Number.isFinite(n)) return min
  return Math.min(max, Math.max(min, n))
}

const formatTime = (date = new Date()) => {
  const pad = (n) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

const statusTextByCode = (code) => {
  if (Number(code) === 1) return '正常'
  if (Number(code) === 2) return '关注'
  if (Number(code) === 3) return '告警'
  return '--'
}

const statusLevelByCode = (code) => {
  if (Number(code) === 3) return 3
  if (Number(code) === 2) return 2
  if (Number(code) === 1) return 1
  return 0
}

// 获取健康度级别（用于颜色分类）——统一走 utils/healthStatus.js 的判定，
// 避免和后端 _score_status()/其他视图各自维护一份 60/30 阈值判断而彼此不一致
const getHealthLevel = () => {
  const status = scoreToStatus(healthScore.value)
  if (status === '正常') return 'good'
  if (status === '故障') return 'warning'
  return 'critical'
}

// 后端 update_dashboard 推送的数据主体，后续显示都从这里取值（接收即显示）
const dashboardData = computed(() => dashboardPayload.value?.data ?? {})
const overview = computed(() => dashboardData.value.overview ?? {})
const health = computed(() => dashboardData.value.health ?? {})
const authorityReplay = computed(() => health.value.authority_replay ?? {})
const authorityReplayActive = computed(() => authorityReplay.value.source_type === 'synthetic_demo')
const authorityReplayTitle = computed(() => {
  if (!authorityReplayActive.value) return '合成演示快照未就绪'
  return `合成演示快照：${authorityReplay.value.row_count || 0} 条缓存，已读取第 ${authorityReplay.value.next_row || 0} 条`
})
const subsystems = computed(() => (Array.isArray(overview.value.subsystems) ? overview.value.subsystems : []))
const signals = computed(() => {
  const raw = overview.value.signals
  return raw && typeof raw === 'object' ? raw : {}
})
const signalEntries = computed(() =>
  Object.entries(signals.value).map(([key, value], index) => ({
    key,
    index,
    label: key.replace(/_/g, ' '),
    value: Number(value) || 0
  }))
)

const historyTrend = computed(() => overview.value.history_trend ?? {})
const historyTimes = computed(() => (Array.isArray(historyTrend.value.times) ? historyTrend.value.times : []))
const historyValues = computed(() =>
  // 趋势值按后端原始数据展示，不再做抖动或平滑
  (Array.isArray(historyTrend.value.values) ? historyTrend.value.values : []).map((v) => Number(v) || 0)
)

// 关系图是后端场景引擎的统一输出：没有导入文件时使用项目内置拓扑，
// 导入后使用 VSDX/Excel 解析出来的节点、边、权重和主要参数。
const runtimeGraph = computed(() => dashboardData.value.overview?.graph || dashboardData.value.health?.graph || null)
const graphIsImported = computed(() => Boolean(runtimeGraph.value && runtimeGraph.value.source_type !== 'builtin'))
const graphNodeCount = computed(() => {
  const nodes = Array.isArray(runtimeGraph.value?.nodes) ? runtimeGraph.value.nodes : []
  return nodes.filter((node) => !node.is_root).length
})
const graphEdgePairs = computed(() => {
  const edges = Array.isArray(runtimeGraph.value?.edges) ? runtimeGraph.value.edges : []
  return edges.length ? edges.map((edge) => [edge.parent, edge.child]) : GRAPH_EDGES
})
const graphRootId = computed(() => runtimeGraph.value?.root_id || GRAPH_ROOT_ID)
const graphRootLabel = computed(() => graphSourceNodes.value.find((node) => node.id === graphRootId.value)?.name || '监控计算机')
const graphSourceNodes = computed(() => {
  const nodes = Array.isArray(runtimeGraph.value?.nodes) ? runtimeGraph.value.nodes : []
  if (nodes.length) return nodes
  return [
    { id: GRAPH_ROOT_ID, name: '监控计算机', is_root: true },
    ...SUBSYSTEMS.map((item) => ({ id: item.id, name: item.name, mapped_subsystem_id: item.id }))
  ]
})

const radarData = computed(() => health.value.radar_data ?? {})
const radarDimensions = computed(() => (Array.isArray(radarData.value.dimensions) ? radarData.value.dimensions : []))
const radarScores = computed(() =>
  // 雷达分数按后端原始数据展示
  (Array.isArray(radarData.value.scores) ? radarData.value.scores : []).map((v) => Number(v) || 0)
)

const displayTimestamp = computed(() => lastUpdated.value || '--')
const deviceLabel = computed(() => `天线节点${overview.value.system_mode ? `-${overview.value.system_mode}` : ''}`)
const healthScore = computed(() => {
  const score = Number(health.value.current_score)
  return Number.isFinite(score) ? score : null
})
const runtimeLabel = computed(() => historyValues.value.length ? `${historyValues.value.length} 个快照` : '--')
const abnormalCount = computed(() => subsystems.value.filter((item) => Number(item.status) !== 1).length)
const leftHealthScore = computed(() => healthScore.value === null ? '--' : Math.round(healthScore.value))
const leftAbnormalCount = computed(() => abnormalCount.value)

// 状态基于健康分数判断，且和 getHealthLevel() 共用同一套阈值（utils/healthStatus.js），
// 避免"高分数+差状态"这类矛盾情况
const systemStatusText = computed(() => healthScore.value === null ? '--' : scoreToStatus(healthScore.value))

const motors = computed(() =>
  (Array.isArray(health.value.parameters) ? health.value.parameters : [])
    .filter((item) => item.dtype !== 'enum' && (String(item.name || '').includes('电机') || item.unit === 'A'))
    .slice(0, 8)
    .map((item) => ({
      name: item.name,
      time: displayTimestamp.value,
      current: `${item.display_value ?? item.value ?? '--'} ${item.unit || ''}`.trim(),
      status: item.status || '--'
    }))
)

const leftMotors = computed(() =>
  motors.value
)

const graphImporting = ref(false)
const graphImportMessage = ref('')
const graphFileInput = ref(null)

const graphParameterText = (node) => {
  const parameter = node.primary_parameter
  if (!parameter) return node.mapped_subsystem_id ? '主要参数待推送' : '未关联参数'
  const value = parameter.display_value ?? parameter.displayValue ?? parameter.value ?? '--'
  return `${parameter.name || parameter.label || '主要参数'} ${value}${parameter.unit ? ` ${parameter.unit}` : ''}`
}

const goGraphNode = (node) => {
  if (node.mapped_subsystem_id) {
    goSubsystem(node.mapped_subsystem_id)
  }
}

const handleGraphFileChange = async (event) => {
  const file = event.target?.files?.[0]
  if (!file) return
  graphImporting.value = true
  graphImportMessage.value = ''
  try {
    const form = new FormData()
    form.append('file', file)
    const response = await axios.post(`${API_PREFIX}/graph/import`, form)
    dashboardPayload.value = response.data?.dashboard || dashboardPayload.value
    graphImportMessage.value = `已导入 ${response.data?.data?.nodes?.filter((node) => !node.is_root)?.length || 0} 个节点`
    heroTab.value = 'graph'
  } catch (error) {
    graphImportMessage.value = error.response?.data?.error || '关系图导入失败'
    console.error('graph import failed', error)
  } finally {
    graphImporting.value = false
    if (event.target) event.target.value = ''
  }
}

const resetImportedGraph = async () => {
  try {
    const response = await axios.post(`${API_PREFIX}/graph/reset`)
    dashboardPayload.value = response.data?.dashboard || dashboardPayload.value
    graphImportMessage.value = '已恢复内置关系图'
  } catch (error) {
    graphImportMessage.value = '恢复内置关系图失败'
    console.error('graph reset failed', error)
  }
}

// 场景引擎推送的参数覆盖 config/params.json 中的演示测点参数；没有收到推送时不显示
// 另一套演示值，避免前端与合成演示快照产生两套信号。
const liveParameterMap = computed(() => {
  const map = {}
  const rows = Array.isArray(health.value.parameters) ? health.value.parameters : []
  rows.forEach((row) => {
    map[row.id] = row
    if (row.param_id) map[row.param_id] = row
  })
  return map
})

// 子系统卡片的主要参数只允许使用当前快照；导入关系图的未知节点可显示导入文件
// 自带的 primary_parameter，但不从本地静态参数伪造实时值。
const resolvePrimaryParameter = (subsystem, fallback = null, preferredName = '') => {
  if (!subsystem) return fallback
  const preferred = String(preferredName || fallback?.name || fallback?.label || subsystem.mainParam?.label || '').trim()
  const signals = Array.isArray(subsystem.signals) ? subsystem.signals : []
  const signal = signals.find((item) => preferred && item.name === preferred) || signals.find((item) => item.name === subsystem.mainParam?.label)
  const live = signal
    ? liveParameterMap.value[`${subsystem.id}-${signal.appendix_no}`] || liveParameterMap.value[signal.id]
    : null
  if (live) {
    return {
      ...live,
      name: live.name || signal?.name || subsystem.mainParam?.label || fallback?.name || fallback?.label || '主要参数',
      display_value: live.display_value ?? live.displayValue ?? live.value ?? '--',
      unit: live.unit ?? signal?.unit ?? subsystem.mainParam?.unit ?? fallback?.unit ?? ''
    }
  }
  if (fallback) {
    return { ...fallback, value: null, display_value: '--', displayValue: '--' }
  }
  return null
}

// 构建所有演示测点参数的列表，前端不另建参数定义
const allParameters = computed(() => {
  const params = []
  SUBSYSTEMS.forEach((subsys) => {
    (subsys.signals || []).forEach((signal) => {
      const id = `${subsys.id}-${signal.appendix_no}`
      const live = liveParameterMap.value[id] || liveParameterMap.value[signal.id]
      params.push({
        id,
        subsystem: subsys.name,
        name: signal.name,
        value: live?.value,
        displayValue: live?.display_value ?? '--',
        threshold: live?.threshold,
        status: live?.status ?? '--',
        unit: live?.unit ?? signal.unit ?? '',
        abnormal: Boolean(live?.abnormal)
      })
    })
  })
  return params
})

// 参数选择状态
const showParamSelector = ref(false)
const selectedParams = ref(new Set([
  // 默认选择前12个参数填满显示区
  ...allParameters.value.slice(0, 12).map(p => p.id)
]))

const toggleParam = (paramId) => {
  if (selectedParams.value.has(paramId)) {
    selectedParams.value.delete(paramId)
  } else {
    selectedParams.value.add(paramId)
  }
  // 强制更新
  selectedParams.value = new Set(selectedParams.value)
}

const removeParam = (paramId) => {
  selectedParams.value.delete(paramId)
  selectedParams.value = new Set(selectedParams.value)
}

// 已选参数的显示数据
const selectedFeedback = computed(() => {
  const result = []
  selectedParams.value.forEach((paramId) => {
    const param = allParameters.value.find(p => p.id === paramId)
    if (param) {
      result.push({
        id: paramId,
        fullName: `${param.subsystem}-${param.name}`,
        time: displayTimestamp.value,
        value: `${param.displayValue ?? param.value} ${param.unit}`,
        threshold: param.threshold,
        status: param.status,
        abnormal: param.abnormal
      })
    }
  })
  return result
})

const feedback = computed(() => {
  const signalRows = (Array.isArray(health.value.parameters) ? health.value.parameters : []).map((item) => ({
    name: item.name || '--',
    time: displayTimestamp.value,
    value: item.display_value ?? item.value ?? '--',
    status: item.status || '--'
  }))
  const radarRows = radarDimensions.value.map((name, index) => ({
    name,
    time: displayTimestamp.value,
    value: `${Math.round(radarScores.value[index] ?? 0)}分`,
    status: scoreToStatus(radarScores.value[index])
  }))
  return [...signalRows, ...radarRows].slice(0, 6)
})

const getFaultParts = (row) => {
  const report = row.fault_report || {}
  const parts = []
  if (report.turntable_system) parts.push('转台系统')
  if (report.geodetic_system) parts.push('大地系统')
  if (report.motor_1) parts.push('电机1')
  if (report.motor_2) parts.push('电机2')
  return parts.length ? parts.join('、') : (report.故障部件 || '--')
}

const faults = computed(() =>
  faultPreviewRows.value.map((row) => ({
    status: row.error_type || '--',
    level: row.error_type || '--',
    time: row.timestamp || '--',
    part: getFaultParts(row),
    duration: '--'
  }))
)

const tick = ref(0)
let tickInterval = null

// 后端拓扑传播后的子系统健康度，按 id 建索引，供下面按需查live值——
// 在还没收到第一次协议回放推送前，统一显示待接收状态，不补造遥测值。
const liveSubsystemMap = computed(() => {
  const map = {}
  const rows = Array.isArray(health.value.subsystems) ? health.value.subsystems : []
  rows.forEach((row) => {
    map[row.id] = row
  })
  return map
})

const subsystemsWithSim = computed(() =>
  SUBSYSTEMS.map((s) => {
    const live = liveSubsystemMap.value[s.id]
    const displayHealth = live && Number.isFinite(Number(live.score)) ? Math.round(Number(live.score)) : '--'
    const primary_parameter = resolvePrimaryParameter(s)
    return {
      ...s,
      _tick: tick.value,
      displayHealth,
      primary_parameter,
      displayParam: primary_parameter ? graphParameterText({ primary_parameter }) : '--',
      statusText: live?.status || '--',
      statusClass: live ? scoreToClass(live.score) : 'status-pending'
    }
  })
)

const graphNodesForDisplay = computed(() => {
  const staticById = Object.fromEntries(SUBSYSTEMS.map((item) => [item.id, item]))
  const parameterBySubsystem = {}
  const parameters = Array.isArray(health.value.parameters) ? health.value.parameters : []
  parameters.forEach((item) => {
    if (!parameterBySubsystem[item.subsystem_id] && item.dtype !== 'enum') {
      parameterBySubsystem[item.subsystem_id] = item
    }
  })
  return graphSourceNodes.value
    .filter((node) => !node.is_root)
    .map((node) => {
      const staticItem = staticById[node.mapped_subsystem_id || node.id]
      const live = liveSubsystemMap.value[node.id] || liveSubsystemMap.value[node.mapped_subsystem_id]
      const rawScore = node.score ?? live?.score
      const score = rawScore == null ? Number.NaN : Number(rawScore)
      const hasScore = Number.isFinite(score)
      const importedPrimary = node.primary_parameter
      const primary = staticItem
        ? resolvePrimaryParameter(
            staticItem,
            importedPrimary || parameterBySubsystem[node.id] || parameterBySubsystem[node.mapped_subsystem_id],
            importedPrimary?.name || importedPrimary?.label
          )
        : importedPrimary || parameterBySubsystem[node.id]
      return {
        ...node,
        displayHealth: hasScore ? Math.round(score) : '--',
        score: hasScore ? score : null,
        status: node.status || (hasScore ? scoreToStatus(score) : '--'),
        statusClass: hasScore ? scoreToClass(score) : 'status-pending',
        mainParam: staticItem?.mainParam,
        primary_parameter: primary,
        mapped_subsystem_id: node.mapped_subsystem_id || staticItem?.id || null
      }
    })
})

const totalParamCount = computed(() => {
  const liveParameters = Array.isArray(health.value.parameters) ? health.value.parameters : []
  if (liveParameters.length) {
    return new Set(liveParameters.map((item) => item.id || `${item.subsystem_id || ''}-${item.param_id || item.name || ''}`)).size
  }
  return '--'
})

// 关系图连线按"下级(箭头发出方)"的状态着色，这里按 id 建一份状态索引，
// 避免在 graphEdgeLines 里为每条边重新遍历 subsystemsWithSim 找状态
const subsystemStatusMap = computed(() => {
  const map = {}
  graphNodesForDisplay.value.forEach((s) => {
    map[s.id] = s.statusClass
  })
  return map
})

// 演示子系统摆进一个 7列x5行(奇数x奇数,保证有唯一正中心格)的对称网格,正中心格
// 固定放雷达图片,其余格子按顺序摆子系统;35格里演示子系统用不完的1格渲染成空
// 占位格——师兄的要求是"块块内容可以有空的,但一定要有一个块块在那,把中间填满,
// 而且对称",不要求格子数量和子系统数量正好对上。
const RING_GRID = { cols: 7, rows: 5 }

const ringGridCells = computed(() => {
  const { cols, rows } = RING_GRID
  const total = cols * rows
  const centerIndex = Math.floor(rows / 2) * cols + Math.floor(cols / 2)
  const items = graphNodesForDisplay.value
  let nextItem = 0
  const cells = []
  for (let i = 0; i < total; i += 1) {
    if (i === centerIndex) {
      cells.push({ type: 'image' })
    } else if (nextItem < items.length) {
      cells.push({ type: 'subsystem', data: items[nextItem] })
      nextItem += 1
    } else {
      cells.push({
        type: 'fill',
        statusClass: healthScore.value === null ? 'status-pending' : scoreToClass(healthScore.value)
      })
    }
  }
  return cells
})

// 部分子系统（如急停按钮、声光报警器等）没有可监测参数（mainParam 为空），
// 详情页会因访问 mainParam.xxx 而崩溃白屏，因此这类子系统禁止点击跳转
const goSubsystem = (id) => {
  const target = SUBSYSTEMS.find((s) => s.id === id)
  if (!target || !target.mainParam) return
  router.push(`/subsystem/${id}`)
}

// 子系统关系图（Tab 2）：监控计算机放在正中心，它的直接下级排在紧贴它的第一圈，
// 这些子系统的下级再排在第二圈，依次向外分层；没有连线的孤立子系统单独放在角落。
// 连线用直线（收缩过端点，不压在卡片上），箭头方向是"下级指向上级"，与拓扑表左列→右列一致。
//
// 之前用监控计算机居中、下级绕一圈一圈摆的放射状布局，容器不够大时最密的一圈（13 个
// 节点）无论怎么调间距都会挤在一起，是几何上的死结。改成从左到右按层分列：监控计算机
// 在最左，下级依次往右排成列，同一列内的卡片纵向均匀摆开，用满整个容器高度；哪一列节点
// 太多导致按基准卡片高度放不下，就自动把这一列的卡片高度缩小，用真实测量的容器像素尺寸
// 保证列内绝不重叠，而不是假设一个固定容器大小。
const heroTab = ref('ring')
const graphStageRef = ref(null)
const graphStageSize = ref({ width: 900, height: 620 })
let graphStageObserver = null

const attachGraphStageObserver = async () => {
  graphStageObserver?.disconnect()
  graphStageObserver = null
  await nextTick()
  if (graphStageRef.value) {
    graphStageObserver = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (!entry) return
      const { width, height } = entry.contentRect
      if (width > 0 && height > 0) {
        graphStageSize.value = { width, height }
      }
    })
    graphStageObserver.observe(graphStageRef.value)
  }
}

onMounted(() => {
  // 关系图位于 v-if 分支，初始渲染是环形总览时 ref 还不存在；监听 tab
  // 切换后重新绑定观察器，确保布局使用真实的关系图容器尺寸，而不是初始
  // 占位尺寸 900x620。
  attachGraphStageObserver()
})

watch(heroTab, (tab) => {
  if (tab === 'graph') attachGraphStageObserver()
  else graphStageObserver?.disconnect()
})

onUnmounted(() => {
  graphStageObserver?.disconnect()
})

const graphCardSize = computed(() => {
  const { width } = graphStageSize.value
  // 节点本身缩窄一些，给列间连线留出空间。高度只是"不拥挤时"的基准值，
  // 最密的列还会由 buildColumnLayout 按容器实际高度继续收缩。
  if (width < 620) return { cardWidth: 72, cardHeight: 34, hubSize: 42 }
  if (width < 860) return { cardWidth: 84, cardHeight: 40, hubSize: 46 }
  return { cardWidth: 90, cardHeight: 42, hubSize: 50 }
})

const graphLayout = computed(() =>
  buildColumnLayout(graphEdgePairs.value, graphRootId.value, {
    extraIds: graphNodesForDisplay.value.map((s) => s.id),
    width: graphStageSize.value.width,
    height: graphStageSize.value.height,
    marginPx: 6,
    gapPx: 4,
    minCardHeight: 16,
    ...graphCardSize.value
  })
)

const graphHubStyle = computed(() => {
  const pos = graphLayout.value.positions[graphRootId.value]
  const size = graphLayout.value.sizes[graphRootId.value]
  if (!pos || !size) return { left: '50%', top: '50%', width: '60px', height: '60px' }
  return { left: `${pos.x}%`, top: `${pos.y}%`, width: `${size.width}px`, height: `${size.height}px` }
})

// 按实际卡片高度缩放字号和内边距。关系图卡片使用单行布局（名称省略 + 健康度），
// 因此即使最密的列只有十几像素高，也不会因为上下两行内容叠加而把底部文字裁掉。
const graphNodes = computed(() =>
  graphNodesForDisplay.value.map((s) => {
    const pos = graphLayout.value.positions[s.id]
    const size = graphLayout.value.sizes[s.id]
    if (!pos || !size) {
      return { ...s, graphStyle: { left: '50%', top: '50%' } }
    }
    const baseH = graphCardSize.value.cardHeight
    const scale = Math.max(0.5, Math.min(1, size.height / baseH))
    return {
      ...s,
      graphStyle: {
        left: `${pos.x}%`,
        top: `${pos.y}%`,
        width: `${size.width}px`,
        height: `${size.height}px`,
        padding: `${Math.max(1, Math.round(3 * scale))}px ${Math.max(2, Math.round(5 * scale))}px`,
        gap: `${Math.max(2, Math.round(4 * scale))}px`,
        '--graph-title-size': `${Math.max(8, Math.round(11 * scale))}px`,
        '--graph-score-size': `${Math.max(9, Math.round(14 * scale))}px`,
        '--graph-param-size': `${Math.max(7, Math.round(9 * scale))}px`
      }
    }
  })
)

// GRAPH_EDGES 里每条边是 [上级, 下级]（对应 上下级拓扑关系.md 的 左列→右列）；箭头方向
// 按需求是"下级指向上级"。跨层关系使用直线，同层关系使用从卡片侧边绕行的曲线，
// 两端都会按对方卡片的矩形边界裁剪，箭头直接落在上级卡片边缘，避免被同列节点遮挡。
// 连线颜色只代表健康状态(绿/黄/红)，由该条边的下级(箭头发出方)当前状态决定——
// 下级健康就是绿色，下级故障/报废就是黄色/红色，和这张卡片本身的边框颜色保持一致。
const graphEdgeLines = computed(() => {
  const layout = graphLayout.value
  const { width, height } = graphStageSize.value

  return graphEdgePairs.value.map(([parent, child], index) => {
    const a = layout.positions[parent]
    const b = layout.positions[child]
    if (!a || !b) return null
    const statusKey = statusKeyFromClass(subsystemStatusMap.value[child])
    const color = STATUS_EDGE_COLORS[statusKey]
    const childHalfWPct = (layout.sizes[child].width / 2 / width) * 100
    const childHalfHPct = (layout.sizes[child].height / 2 / height) * 100
    const parentHalfWPct = (layout.sizes[parent].width / 2 / width) * 100
    const parentHalfHPct = (layout.sizes[parent].height / 2 / height) * 100
    const sameColumn = layout.depth?.get(parent) === layout.depth?.get(child)
    const curve = buildRelationshipPath(
      b,
      a,
      childHalfWPct,
      childHalfHPct,
      parentHalfWPct,
      parentHalfHPct,
      {
        sameColumn,
        // 同层连线左右交替绕行，避免多条曲线叠在同一侧。
        routeSide: index % 2 === 0 ? 1 : -1
      }
    )
    return { curve, color, statusKey, sameColumn }
  }).filter(Boolean)
})

const heroTitle = computed(() => `${overview.value.system_mode || '--'} 模式 / 天线节点`)

const trendPlotPoints = computed(() => {
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

const trendScorePolyline = computed(() =>
  trendPlotPoints.value.length ? trendPlotPoints.value.map((p) => `${p.x},${p.yScore}`).join(' ') : ''
)

const trendFaultPolyline = computed(() =>
  trendPlotPoints.value.length ? trendPlotPoints.value.map((p) => `${p.x},${p.yFault}`).join(' ') : ''
)

const shortDate = (value) => {
  if (!value) return '--'
  const s = String(value)
  return s.includes('-') ? s.slice(5) : s
}

const alarmInfo = computed(() => {
  const firstAbnormal = subsystems.value.find((item) => Number(item.status) > 1)
  if (!firstAbnormal) {
    return {
      description: '当前未检测到子系统异常报警。',
      phenomenon: `系统模式 ${overview.value.system_mode || '--'}，整体状态 ${systemStatusText.value}。`,
      cause: '等待后端推送新的诊断结果。'
    }
  }

  return {
    description: `${firstAbnormal.name || '子系统'}状态为${statusTextByCode(firstAbnormal.status)}。`,
    phenomenon: `健康分 ${healthScore.value}，异常子系统数量 ${abnormalCount.value}。`,
    cause: '来源于 dashboard_json 子系统状态判定结果。'
  }
})

const scenarioMode = computed(() => overview.value.scenario?.mode || health.value.scenario?.mode || 'normal')
const scenarioLabel = computed(() => overview.value.scenario?.label || health.value.scenario?.label || '正常运行')
const scenarioModes = [
  { key: 'normal', label: '正常运行', shortLabel: '正常', shortcut: '0', tone: 'normal' },
  { key: 'azimuth_fault', label: '方位驱动故障', shortLabel: '方位故障', shortcut: '1', tone: 'fault' },
  { key: 'elevation_fault', label: '俯仰驱动故障', shortLabel: '俯仰故障', shortcut: '2', tone: 'fault' },
  { key: 'tracking_fault', label: '测控跟踪故障', shortLabel: '测控故障', shortcut: '3', tone: 'fault' },
  { key: 'environment_fault', label: '环控故障', shortLabel: '环控故障', shortcut: '4', tone: 'fault' },
  { key: 'global_degradation', label: '全局退化', shortLabel: '全局退化', shortcut: '5', tone: 'degradation' }
]
const activeScenarioMode = computed(() => scenarioMode.value)
const scenarioSwitching = ref(false)
const scenarioShortcutTitle = '场景快捷键：0正常 1方位 2俯仰 3测控 4环控 5全局退化'
const scenarioShortcuts = {
  '0': 'normal',
  '1': 'azimuth_fault',
  '2': 'elevation_fault',
  '3': 'tracking_fault',
  '4': 'environment_fault',
  '5': 'global_degradation'
}

const selectScenarioMode = async (mode) => {
  if (!scenarioModes.some((item) => item.key === mode) || mode === scenarioMode.value || scenarioSwitching.value) return
  scenarioSwitching.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/scenario/mode`, { mode })
    if (response.data?.dashboard) {
      dashboardPayload.value = response.data.dashboard
      lastUpdated.value = formatTime()
    }
    await fetchFaultPreview()
  } catch (error) {
    console.error('scenario mode switch failed', error)
  } finally {
    scenarioSwitching.value = false
  }
}

const triggerScenarioByKey = async (event) => {
  if (event.defaultPrevented || event.target?.matches?.('input, textarea, select, button')) return
  const mode = scenarioShortcuts[event.key]
  if (!mode) return
  await selectScenarioMode(mode)
}

const maxAlarmLevel = computed(() =>
  subsystems.value.reduce((max, item) => Math.max(max, statusLevelByCode(item.status)), 0)
)

const hasActiveAlarm = computed(() => maxAlarmLevel.value >= 2)
const alarmSeverity = computed(() => (maxAlarmLevel.value >= 3 ? 'critical' : 'warning'))
const alarmBannerIcon = computed(() => (alarmSeverity.value === 'critical' ? '!' : '≈'))
const alarmBannerText = computed(() => {
  if (alarmSeverity.value === 'critical') {
    return `严重故障：${abnormalCount.value} 项异常，点击查看`
  }
  return `一般故障：${abnormalCount.value} 项异常，点击查看`
})

const fetchFaultPreview = async () => {
  try {
    const res = await axios.get(`${API_PREFIX}/errors`, {
      params: { page: 1, page_size: 5, sort: 'DESC' }
    })
    faultPreviewRows.value = res.data?.items || []
  } catch (error) {
    faultPreviewRows.value = []
    console.error('fetchFaultPreview failed', error)
  }
}

const fetchHealthTrend = async () => {
  try {
    const res = await axios.get(`${API_PREFIX}/health/daily-report`)
    dailyScores.value = Array.isArray(res.data?.data) ? res.data.data : []
  } catch (error) {
    dailyScores.value = []
    console.error('fetchHealthTrend failed', error)
  }
}

onMounted(() => {
  window.addEventListener('keydown', triggerScenarioByKey)
  dashboardSocket = createDashboardSocket({
    onDashboardUpdate: (payload) => {
      // 接收到后端 JSON 后直接更新页面数据
      dashboardPayload.value = payload
      lastUpdated.value = formatTime()
      // 每次后端推送后刷新故障预览，确保与 fault-history 首页数据顺序一致
      fetchFaultPreview()
    }
  })
  fetchFaultPreview()
  // 健康趋势图使用 alerts 页面同源数据
  fetchHealthTrend()
})

onUnmounted(() => {
  window.removeEventListener('keydown', triggerScenarioByKey)
  if (dashboardSocket) {
    dashboardSocket.disconnect()
    dashboardSocket = null
  }
})
</script>

<style scoped>
.health-screen {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  width: 100%;
  height: 100vh;
  min-height: 0;
  color: #d4f7ff;
  background:
    radial-gradient(circle at 25% 10%, rgba(30, 136, 255, 0.12), transparent 35%),
    radial-gradient(circle at 85% 0%, rgba(0, 192, 255, 0.08), transparent 30%),
    linear-gradient(180deg, #020b1f 0%, #05183d 50%, #03102b 100%);
  border: 1px solid #0f3a6d;
  border-radius: 14px;
  padding: 8px;
  box-shadow:
    inset 0 0 50px rgba(0, 100, 200, 0.18),
    0 0 20px rgba(0, 120, 220, 0.18);
}

.corner-alarm {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border-radius: 999px;
  padding: 8px 12px 8px 10px;
  border: 1px solid rgba(255, 255, 255, 0.22);
  cursor: pointer;
  color: #fff;
  background: rgba(8, 20, 46, 0.88);
  box-shadow: 0 0 10px rgba(0, 0, 0, 0.22);
  animation: alarmPulse 1s ease-in-out infinite;
}

.corner-alarm-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-weight: 800;
  line-height: 1;
  font-size: 15px;
  background: rgba(255, 255, 255, 0.08);
}

.corner-alarm-text {
  font-size: 12px;
  letter-spacing: 0.5px;
  white-space: nowrap;
}

.corner-alarm.severity-warning {
  border-color: rgba(255, 224, 102, 0.55);
  color: #fff6bf;
  background: linear-gradient(180deg, rgba(90, 66, 8, 0.92), rgba(58, 43, 6, 0.92));
  box-shadow:
    0 0 14px rgba(255, 217, 90, 0.35),
    inset 0 0 12px rgba(255, 202, 72, 0.16);
}

.corner-alarm.severity-warning .corner-alarm-icon {
  color: #2e2200;
  background: radial-gradient(circle, #ffe46f, #ffbf3d);
  box-shadow: 0 0 10px rgba(255, 216, 87, 0.45);
}

.corner-alarm.severity-critical {
  border-color: rgba(255, 107, 124, 0.62);
  color: #ffe1e6;
  background: linear-gradient(180deg, rgba(108, 14, 28, 0.92), rgba(69, 8, 16, 0.92));
  box-shadow:
    0 0 16px rgba(255, 82, 109, 0.36),
    inset 0 0 14px rgba(255, 95, 95, 0.18);
}

.corner-alarm.severity-critical .corner-alarm-icon {
  color: #fff;
  background: radial-gradient(circle, #ff5f74, #d31735);
  box-shadow: 0 0 12px rgba(255, 91, 114, 0.52);
}

@keyframes alarmPulse {
  0%, 100% {
    opacity: 1;
    transform: scale(1);
  }
  50% {
    opacity: 0.55;
    transform: scale(1.02);
  }
}

.health-screen::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(rgba(60, 150, 255, 0.05) 1px, transparent 1px),
    linear-gradient(90deg, rgba(60, 150, 255, 0.05) 1px, transparent 1px);
  background-size: 40px 40px;
}

.screen-header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  padding: 6px 10px;
  border: 1px solid rgba(25, 118, 210, 0.55);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 35, 82, 0.92), rgba(4, 20, 54, 0.92));
  box-shadow: inset 0 0 16px rgba(0, 120, 220, 0.12);
}

.screen-title {
  margin: 0;
  font-size: clamp(24px, 2vw, 34px);
  color: #f4fbff;
  letter-spacing: 3px;
  text-shadow: 0 0 14px rgba(74, 200, 255, 0.55);
  text-transform: uppercase;
}

.header-nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.header-nav-right {
  justify-content: flex-end;
}

.tab-chip {
  padding: 7px 13px;
  border: 1px solid rgba(60, 170, 255, 0.45);
  border-radius: 6px;
  color: #9be4ff;
  background: linear-gradient(180deg, rgba(10, 45, 100, 0.88), rgba(6, 28, 70, 0.88));
  font-size: 13px;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.2s ease;
}

.tab-chip:hover {
  transform: translateY(-1px);
  color: #e0f8ff;
  border-color: #5cd8ff;
  background: linear-gradient(180deg, rgba(18, 70, 145, 0.92), rgba(10, 45, 100, 0.92));
  box-shadow: 0 0 12px rgba(74, 213, 255, 0.35);
}

.screen-main {
  display: grid;
  gap: 8px;
  grid-template-columns: 280px 1fr 300px;
  height: calc(100vh - 78px);
  min-height: 0;
}

.panel-box {
  border: 1px solid rgba(25, 118, 210, 0.55);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 31, 80, 0.9), rgba(4, 18, 50, 0.92));
  box-shadow:
    inset 0 0 14px rgba(0, 100, 200, 0.12),
    0 0 8px rgba(0, 100, 200, 0.12);
  backdrop-filter: blur(2px);
  position: relative;
}

.panel-box::after {
  content: "";
  position: absolute;
  inset: 5px;
  border: 1px solid rgba(80, 180, 255, 0.08);
  border-radius: 8px;
  pointer-events: none;
}

.card-title {
  margin: 0;
  font-size: 15px;
  color: #9be9ff;
}

.live-jitter {
  display: inline-block;
  will-change: transform;
  transition: transform 0.16s linear;
}

.meta-row {
  margin-top: 8px;
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: #7ddcff;
}

.left-col {
  display: grid;
  gap: 8px;
  grid-template-rows: auto 1fr;
  min-height: 0;
}

.right-col {
  display: grid;
  gap: 8px;
  /* 右列第一个子卡是 telemetry-card（滚动列表），第二个是 alarm-card（固定几行文字）——
     和左列子卡顺序相反，1fr 必须给第一个才能让滚动区真正撑满剩余空间 */
  grid-template-rows: 1fr auto;
  min-height: 0;
}

.info-card,
.chart-card,
.list-card,
.telemetry-card,
.alarm-card {
  padding: 6px;
}

.list-card,
.telemetry-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.stats-grid {
  margin-top: 10px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.stat-item {
  border: 1px solid rgba(63, 207, 255, 0.25);
  border-radius: 8px;
  background: rgba(9, 29, 77, 0.6);
  padding: 8px;
  box-shadow: inset 0 0 12px rgba(22, 162, 255, 0.18);
}

.label {
  margin: 0;
  color: #79cbe8;
  font-size: 11px;
}

.value {
  margin: 3px 0 0;
  font-size: 22px;
  font-weight: 700;
}

.center-col {
  display: grid;
  gap: 8px;
  grid-template-rows: minmax(0, 1fr) minmax(150px, 0.42fr);
  min-height: 0;
}

.hero-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
  padding: 8px 12px 12px;
}

.ring-center-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  border-radius: 10px;
  filter: drop-shadow(0 0 18px rgba(0, 150, 255, 0.25));
}

.hero-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  color: #9adfff;
  padding: 4px 0 8px;
  border-bottom: 1px solid rgba(118, 214, 255, 0.22);
}

/* The reference shell leaves less width for the legacy three-column view.
   Keep the middle title readable instead of allowing flexbox to wrap it one
   character per line when the window is around 1100–1280px wide. */
.hero-top > span {
  min-width: 0;
  flex: 1 1 auto;
  overflow: hidden;
  text-align: center;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.scenario-toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-height: 34px;
  padding: 6px 0 4px;
}

.scenario-toolbar-label {
  margin-right: 2px;
  color: #8dd8f1;
  font-size: 11px;
  white-space: nowrap;
}

.scenario-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 26px;
  padding: 4px 8px;
  border: 1px solid rgba(108, 216, 255, 0.3);
  border-radius: 6px;
  color: #c6ecff;
  background: rgba(12, 42, 82, 0.9);
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  white-space: nowrap;
  transition: 0.2s ease;
}

.scenario-btn:hover:not(:disabled),
.scenario-btn.active {
  color: #f5fdff;
  border-color: #5cd8ff;
  background: linear-gradient(180deg, rgba(25, 92, 173, 0.95), rgba(18, 58, 116, 0.95));
  box-shadow: 0 0 9px rgba(89, 205, 255, 0.25);
}

.scenario-btn:disabled {
  cursor: wait;
  opacity: 0.55;
}

.scenario-btn-fault.active,
.scenario-btn-fault:hover:not(:disabled) {
  border-color: #ffb25c;
  background: linear-gradient(180deg, rgba(129, 74, 23, 0.95), rgba(74, 43, 16, 0.95));
  box-shadow: 0 0 9px rgba(255, 179, 74, 0.24);
}

.scenario-btn-degradation.active,
.scenario-btn-degradation:hover:not(:disabled) {
  border-color: #ff6b7c;
  background: linear-gradient(180deg, rgba(125, 30, 51, 0.95), rgba(72, 18, 33, 0.95));
  box-shadow: 0 0 9px rgba(255, 91, 107, 0.24);
}

.scenario-key {
  display: inline-grid;
  place-items: center;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  color: #07152b;
  background: #a9eaff;
  font-size: 10px;
  font-weight: 800;
}

.scenario-shortcut-note {
  margin-left: auto;
  color: #6fa8c4;
  font-size: 10px;
  white-space: nowrap;
}

.sim-toggle {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  background: linear-gradient(180deg, #19467f, #12345f);
  color: #c6ecff;
  font-size: 12px;
  cursor: pointer;
  transition: 0.2s ease;
}

.sim-toggle.active {
  background: linear-gradient(180deg, #1f5cad, #153f84);
  border-color: #5cd8ff;
  color: #e6fbff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.25);
}

.hero-tabs {
  display: flex;
  gap: 6px;
}

.hero-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
}

.graph-import-btn,
.graph-reset-btn {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 5px 10px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  border-radius: 6px;
  background: linear-gradient(180deg, #12345f, #0c2547);
  color: #9be4ff;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  white-space: nowrap;
}

.graph-import-btn:hover,
.graph-reset-btn:hover {
  color: #e6fbff;
  border-color: #5cd8ff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.2);
}

.graph-import-btn.disabled {
  opacity: 0.55;
  cursor: wait;
}

.graph-import-btn input {
  display: none;
}

.hero-tab-btn {
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid rgba(108, 216, 255, 0.35);
  background: linear-gradient(180deg, #12345f, #0c2547);
  color: #9be4ff;
  font-size: 12px;
  cursor: pointer;
  font-family: inherit;
  transition: 0.2s ease;
}

.hero-tab-btn.active {
  background: linear-gradient(180deg, #1f5cad, #153f84);
  border-color: #5cd8ff;
  color: #e6fbff;
  box-shadow: 0 0 10px rgba(89, 205, 255, 0.25);
}

/* 演示子系统摆进 7x5 对称网格，正中心格固定放雷达图片，不再用极坐标环绕布局 */
.hero-body {
  position: relative;
  flex: 1;
  min-height: 0;
  padding: 8px;
}

.ring-stage {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  grid-template-rows: repeat(5, 1fr);
  gap: 5px;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.ring-cell {
  position: relative;
  display: flex;
  min-width: 0;
  min-height: 0;
  align-items: center;
  justify-content: center;
}

.ring-cell--empty {
  border: 1px dashed rgba(80, 200, 255, 0.12);
  border-radius: 10px;
  background: rgba(4, 22, 48, 0.25);
}

.ring-fill {
  width: 100%;
  height: 100%;
  border: 1px solid rgba(80, 200, 255, 0.12);
  border-radius: 10px;
  background: linear-gradient(160deg, rgba(4, 22, 48, 0.72), rgba(8, 44, 70, 0.62));
  box-shadow: inset 0 0 14px rgba(80, 200, 255, 0.08);
}

.ring-fill.status-ok {
  border-color: rgba(68, 242, 166, 0.42);
  background: linear-gradient(160deg, rgba(68, 242, 166, 0.32), rgba(4, 22, 48, 0.72));
}

.ring-fill.status-warn {
  border-color: rgba(255, 211, 101, 0.5);
  background: linear-gradient(160deg, rgba(255, 211, 101, 0.34), rgba(4, 22, 48, 0.72));
}

.ring-fill.status-danger {
  border-color: rgba(255, 91, 107, 0.58);
  background: linear-gradient(160deg, rgba(255, 91, 107, 0.38), rgba(4, 22, 48, 0.72));
}

.ring-card {
  width: calc(100% - 8px);
  height: calc(100% - 6px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: 1.5px solid rgba(80, 200, 255, 0.25);
  border-radius: 10px;
  background: rgba(4, 22, 48, 0.78);
  padding: 4px 6px;
  cursor: pointer;
  text-align: center;
  transition: 0.2s ease;
}

.ring-card:hover {
  border-color: rgba(120, 220, 255, 0.6);
  box-shadow: 0 0 12px rgba(0, 120, 220, 0.3);
  z-index: 5;
}

.ring-card h3 {
  margin: 0;
  width: 100%;
  min-width: 0;
  font-size: 11px;
  color: #f2fbff;
  line-height: 1.1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ring-card strong {
  flex-shrink: 0;
  font-size: 15px;
  font-weight: 700;
  line-height: 1;
  color: #e6fbff;
}

.ring-card.status-ok {
  border-color: #44f2a6;
  background: linear-gradient(160deg, rgba(68, 242, 166, 0.62), rgba(4, 22, 48, 0.72));
  box-shadow: inset 0 0 18px rgba(68, 242, 166, 0.45), 0 0 10px rgba(68, 242, 166, 0.3);
}

.ring-card.status-ok strong {
  color: #8ffcc9;
}

.ring-card.status-warn {
  border-color: #ffd365;
  background: linear-gradient(160deg, rgba(255, 211, 101, 0.62), rgba(4, 22, 48, 0.72));
  box-shadow: inset 0 0 18px rgba(255, 211, 101, 0.48), 0 0 10px rgba(255, 211, 101, 0.32);
}

.ring-card.status-warn strong {
  color: #ffe6a8;
}

.ring-card.status-danger {
  border-color: #ff5b6b;
  background: linear-gradient(160deg, rgba(255, 91, 107, 0.64), rgba(4, 22, 48, 0.72));
  box-shadow: inset 0 0 18px rgba(255, 91, 107, 0.5), 0 0 10px rgba(255, 91, 107, 0.34);
}

.ring-card.status-danger strong {
  color: #ffb0b8;
}

.ring-card.is-disabled,
.graph-card.is-disabled {
  cursor: default;
  opacity: 0.55;
  filter: grayscale(0.3);
}

.ring-card.is-disabled:hover,
.graph-card.is-disabled:hover {
  border-color: rgba(80, 200, 255, 0.25);
  box-shadow: none;
}

/* 子系统关系图（Tab 2）：监控计算机在最左，下级按层从左到右分列，列内纵向铺满整栏高度 */
.graph-stage {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 0;
}

.ring-param,
.graph-param {
  max-width: 100%;
  color: #9be4ff;
  font-size: 9px;
  line-height: 1.15;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.graph-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  overflow: visible;
}

.graph-edge {
  fill: none;
  stroke-width: 1.7;
  stroke-linecap: round;
  opacity: 0.95;
  vector-effect: non-scaling-stroke;
}

.graph-edge-same-column {
  stroke-width: 2.1;
}

.graph-hub-node {
  position: absolute;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  border: 1px dashed rgba(120, 220, 255, 0.5);
  background: rgba(4, 22, 48, 0.6);
  color: #7ddcff;
  font-size: 10px;
  text-align: center;
  z-index: 1;
}

.graph-card {
  position: absolute;
  transform: translate(-50%, -50%);
  z-index: 2;
  display: flex;
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
  gap: 4px;
  width: 70px;
  height: 42px;
  overflow: hidden;
  border: 2px solid rgba(80, 200, 255, 0.25);
  border-radius: 10px;
  background: rgba(4, 22, 48, 0.9);
  padding: 6px 8px;
  cursor: pointer;
  text-align: center;
  transition: 0.2s ease;
}

.graph-card:hover {
  border-color: rgba(120, 220, 255, 0.6);
  box-shadow: 0 0 12px rgba(0, 120, 220, 0.3);
  z-index: 5;
}

.graph-card h3 {
  margin: 0;
  min-width: 0;
  flex: 1 1 auto;
  font-size: var(--graph-title-size, 10px);
  color: #f2fbff;
  line-height: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.graph-card strong {
  flex: 0 0 auto;
  white-space: nowrap;
  font-size: var(--graph-score-size, 13px);
  font-weight: 700;
  color: #e6fbff;
  line-height: 1;
}

.graph-card .graph-param {
  max-width: 100%;
  font-size: var(--graph-param-size, 9px);
  line-height: 1.1;
}

.graph-card.status-ok {
  border-color: #44f2a6;
  background: linear-gradient(160deg, rgba(68, 242, 166, 0.6), rgba(4, 22, 48, 0.78));
  box-shadow: inset 0 0 16px rgba(68, 242, 166, 0.42);
}

.graph-card.status-ok strong {
  color: #8ffcc9;
}

.graph-card.status-warn {
  border-color: #ffd365;
  background: linear-gradient(160deg, rgba(255, 211, 101, 0.6), rgba(4, 22, 48, 0.78));
  box-shadow: inset 0 0 16px rgba(255, 211, 101, 0.45);
}

.graph-card.status-warn strong {
  color: #ffe6a8;
}

.graph-card.status-danger {
  border-color: #ff5b6b;
  background: linear-gradient(160deg, rgba(255, 91, 107, 0.62), rgba(4, 22, 48, 0.78));
  box-shadow: inset 0 0 16px rgba(255, 91, 107, 0.48);
}

.graph-card.status-danger strong {
  color: #ffb0b8;
}

/* 大号健康分数卡片 */
.health-score-hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  max-width: 200px;
  margin: 0 auto 3px;
  padding: 6px;
  background: linear-gradient(135deg, rgba(255, 105, 180, 0.15), rgba(255, 200, 200, 0.08));
  border-radius: 12px;
  border: 1px solid rgba(255, 150, 200, 0.3);
  box-shadow: inset 0 0 15px rgba(255, 105, 180, 0.1);
}

.health-score-hero.health-level-good {
  background: linear-gradient(135deg, rgba(68, 242, 166, 0.2), rgba(68, 242, 166, 0.06));
  border-color: rgba(68, 242, 166, 0.48);
  box-shadow: inset 0 0 18px rgba(68, 242, 166, 0.14);
}

.health-score-hero.health-level-warning {
  background: linear-gradient(135deg, rgba(255, 91, 107, 0.22), rgba(255, 91, 107, 0.06));
  border-color: rgba(255, 91, 107, 0.54);
  box-shadow: inset 0 0 18px rgba(255, 91, 107, 0.16);
}

.health-score-hero.health-level-critical {
  background: linear-gradient(135deg, rgba(255, 91, 107, 0.24), rgba(255, 91, 107, 0.06));
  border-color: rgba(255, 91, 107, 0.58);
  box-shadow: inset 0 0 18px rgba(255, 91, 107, 0.18);
}

.health-score-hero.health-level-good .score-number {
  color: #4bffa9;
  text-shadow: 0 0 20px rgba(68, 242, 166, 0.42);
}

.health-score-hero.health-level-warning .score-number {
  color: #ff5b6b;
  text-shadow: 0 0 20px rgba(255, 91, 107, 0.42);
}

.health-score-hero.health-level-critical .score-number {
  color: #ff5b6b;
  text-shadow: 0 0 20px rgba(255, 91, 107, 0.42);
}

.score-number {
  font-size: 140px;
  font-weight: 900;
  color: #ff69b4;
  line-height: 0.9;
  letter-spacing: -2px;
  text-shadow: 0 0 20px rgba(255, 105, 180, 0.4);
}

.score-label {
  font-size: 30px;
  color: #9be9ff;
  margin-top: -8px;
  letter-spacing: 0.5px;
  font-weight: 700;
}

.score-status {
  font-size: 20px;
  padding: 10px 20px;
  border-radius: 999px;
  margin-top: 10px;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.score-status.status-good {
  background: rgba(68, 242, 166, 0.25);
  color: #4bffa9;
  border: 1px solid rgba(68, 242, 166, 0.4);
}

.score-status.status-warning {
  background: rgba(255, 213, 101, 0.25);
  color: #ffe56b;
  border: 1px solid rgba(255, 213, 101, 0.4);
}

.score-status.status-critical {
  background: rgba(255, 91, 107, 0.25);
  color: #ff5b6b;
  border: 1px solid rgba(255, 91, 107, 0.4);
}

/* 次要统计信息 */
.stats-grid-secondary {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 2px;
}

/* 自动滚动容器 */
.auto-scroll-container {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  position: relative;
  display: flex;
  flex-direction: column;
}

.auto-scroll-container .row-item {
  animation: scrollUpAutomatic 15s linear infinite;
  min-height: 50px;
  align-items: center;
  opacity: 1;
}

@keyframes scrollUpAutomatic {
  0% {
    transform: translateY(0);
    opacity: 1;
  }
  85% {
    opacity: 1;
  }
  100% {
    transform: translateY(-100px);
    opacity: 0;
  }
}

/* 故障日志专用滚动样式 */
.log-scroll {
  max-height: 150px;
}

.log-scroll .row-item {
  animation-duration: 18s;
}

.hero-caption {
  margin: 8px 0 0;
  text-align: center;
  font-size: 12px;
  color: #8dd8f1;
  letter-spacing: 0.5px;
}

.graph-import-message {
  margin-left: 8px;
  color: #ffe56b;
}

.authority-replay-hint {
  display: inline-block;
  margin-left: 8px;
  padding: 1px 6px;
  border: 1px solid rgba(68, 242, 166, 0.65);
  border-radius: 999px;
  color: #77ffc1;
  font-size: 11px;
}

.bottom-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: 1.2fr 1fr;
}

.table-card,
.trend-card {
  padding: 6px;
}

.trend-card {
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.log-entry {
  cursor: pointer;
  transition: all 0.2s ease;
}

.log-entry:hover {
  transform: translateY(-1px);
  border-color: rgba(106, 229, 255, 0.92);
  box-shadow:
    inset 0 0 22px rgba(0, 180, 255, 0.24),
    0 0 14px rgba(45, 189, 255, 0.35);
}

.trend-entry {
  cursor: pointer;
  transition: all 0.2s ease;
}

.trend-entry:hover {
  transform: translateY(-1px);
  border-color: rgba(106, 229, 255, 0.92);
  box-shadow:
    inset 0 0 22px rgba(0, 180, 255, 0.24),
    0 0 14px rgba(45, 189, 255, 0.35);
}

.row-head,
.row-item {
  display: grid;
  grid-template-columns: 1.2fr 1.5fr 0.8fr;
  gap: 10px;
  font-size: 12px;
}

/* 天线反馈的行不是多列表格，是"标签+竖排数值/时间+删除按钮"的横向排布，
   用 flex 而不是 grid——所以这里单独声明 display:flex，不能让下面 .row-item
   的通用 grid 布局套用到它头上 */
.telemetry-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.data-section {
  display: flex;
  flex-direction: column;
  gap: 2px;
  align-items: flex-start;
}

.data-value {
  font-weight: 600;
  color: #5cd8ff;
}

.data-time {
  font-size: 11px;
  color: #8dd8f1;
  opacity: 0.8;
}

.table-card .row-head,
.table-card .row-item {
  grid-template-columns: 1fr 1fr 1.3fr 1fr 0.8fr;
}

/* 电机运行状态监测是测点名称/数据时间/电流/状态 4 列，比默认的 3 列模板多一列——
   之前没有这条覆盖规则时，第4列(状态)会被挤到 grid 的下一隐式行，表现为表头
   "状态"单独换行、数据行文字挤在一起没法对齐 */
.list-card .row-head,
.list-card .row-item {
  grid-template-columns: 1.3fr 1.4fr 0.9fr 0.7fr;
}

.row-head {
  margin-top: 10px;
  color: #81dfff;
  padding-bottom: 6px;
  border-bottom: 1px solid rgba(125, 227, 255, 0.25);
}

.row-item {
  padding: 6px 0;
  color: #d9f6ff;
  border-bottom: 1px solid rgba(56, 143, 195, 0.2);
}

.row-item .param-label {
  flex: 1;
  min-width: 0;
  word-break: break-word;
  font-size: 12px;
}

.delete-btn {
  flex-shrink: 0;
  padding: 2px 8px;
  background: rgba(255, 91, 107, 0.25);
  border: 1px solid rgba(255, 91, 107, 0.4);
  color: #ff5b6b;
  border-radius: 4px;
  cursor: pointer;
  font-size: 11px;
  transition: 0.2s ease;
}

.delete-btn:hover {
  background: rgba(255, 91, 107, 0.45);
  border-color: rgba(255, 91, 107, 0.6);
}

/* 天线反馈头部 */
.telemetry-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.param-selector-btn {
  padding: 4px 10px;
  background: rgba(80, 200, 255, 0.2);
  border: 1px solid rgba(80, 200, 255, 0.4);
  color: #5cd8ff;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: 0.2s ease;
}

.param-selector-btn:hover {
  background: rgba(80, 200, 255, 0.3);
  border-color: rgba(80, 200, 255, 0.6);
}

/* 参数选择模态框 */
.param-selector-modal {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  background: rgba(6, 24, 56, 0.95);
  border: 2px solid rgba(80, 200, 255, 0.4);
  border-radius: 8px;
  padding: 0;
  z-index: 1000;
  width: 90%;
  max-width: 400px;
  max-height: 70vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
}

.modal-header {
  padding: 12px;
  border-bottom: 1px solid rgba(80, 200, 255, 0.2);
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #5cd8ff;
  font-weight: 600;
}

.modal-header button {
  background: none;
  border: none;
  color: #5cd8ff;
  cursor: pointer;
  font-size: 18px;
}

.param-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.param-item {
  padding: 8px 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  border-bottom: 1px solid rgba(80, 200, 255, 0.1);
  transition: 0.2s ease;
}

.param-item:hover {
  background: rgba(80, 200, 255, 0.15);
}

.param-item input[type="checkbox"] {
  cursor: pointer;
}

.param-name {
  font-size: 12px;
  color: #d9f6ff;
  flex: 1;
  word-break: break-all;
}

.modal-footer {
  padding: 12px;
  border-top: 1px solid rgba(80, 200, 255, 0.2);
  text-align: right;
}

.close-btn {
  padding: 6px 14px;
  background: rgba(68, 242, 166, 0.25);
  border: 1px solid rgba(68, 242, 166, 0.4);
  color: #4bffa9;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: 0.2s ease;
}

.close-btn:hover {
  background: rgba(68, 242, 166, 0.4);
  border-color: rgba(68, 242, 166, 0.6);
}

/* 天线反馈显示区 */
.telemetry-display {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  margin-top: 8px;
}

.telemetry-rows-scroll {
  flex: 1;
  min-height: 80px;
  overflow-y: scroll;
  border: 1px solid rgba(80, 200, 255, 0.15);
  border-radius: 4px;
  padding: 4px 0;
}

.telemetry-rows-scroll::-webkit-scrollbar {
  width: 8px;
}

.telemetry-rows-scroll::-webkit-scrollbar-track {
  background: rgba(80, 200, 255, 0.1);
  border-radius: 4px;
}

.telemetry-rows-scroll::-webkit-scrollbar-thumb {
  background: rgba(80, 200, 255, 0.4);
  border-radius: 4px;
}

.telemetry-rows-scroll::-webkit-scrollbar-thumb:hover {
  background: rgba(80, 200, 255, 0.6);
}

.trend-wrap {
  margin-top: 10px;
  background: rgba(6, 43, 91, 0.5);
  border: 1px solid rgba(83, 203, 255, 0.25);
  border-radius: 8px;
  padding: 8px;
  box-shadow: inset 0 0 12px rgba(80, 205, 255, 0.15);
}

.trend-card .trend-wrap {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  margin-top: 6px;
}

.trend-svg {
  flex: 1 1 auto;
  width: 100%;
  height: 100%;
  min-height: 0;
  display: block;
  padding: 4px;
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(6, 21, 57, 0.25), rgba(6, 21, 57, 0.12));
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

.alarm-card {
  display: grid;
  gap: 8px;
}

.alarm-entry {
  cursor: pointer;
  transition: all 0.2s ease;
}

.alarm-entry:hover {
  transform: translateY(-1px);
  border-color: rgba(106, 229, 255, 0.92);
  box-shadow:
    inset 0 0 22px rgba(0, 180, 255, 0.24),
    0 0 14px rgba(45, 189, 255, 0.35);
}

.alarm-row {
  display: grid;
  grid-template-columns: 70px 1fr;
  border: 1px solid rgba(125, 220, 255, 0.23);
}

.alarm-row span {
  background: rgba(0, 136, 255, 0.35);
  padding: 10px;
  color: #b7f3ff;
  font-size: 13px;
}

.alarm-row p {
  margin: 0;
  padding: 10px;
  color: #d9f6ff;
  font-size: 13px;
}

.accent-green {
  color: #4bffa9;
}

.accent-cyan {
  color: #57eaff;
}

.accent-pink {
  color: #ff87cd;
}

.accent-yellow {
  color: #ffe56b;
}

/* 常见 1366×768 等低高度桌面屏幕：缩小边距和字号，但保留三栏布局。 */
@media (min-width: 1101px) and (max-height: 820px) {
  .health-screen {
    padding: 6px;
  }

  .screen-header {
    margin-bottom: 6px;
    padding: 5px 8px;
  }

  .screen-main {
    height: calc(100vh - 68px);
    gap: 6px;
    grid-template-columns: 190px minmax(0, 1fr) 205px;
  }

  .left-col,
  .right-col,
  .center-col {
    gap: 6px;
  }

  .info-card,
  .chart-card,
  .list-card,
  .telemetry-card,
  .alarm-card {
    padding: 5px;
  }

  .ring-card {
    gap: 2px;
    padding: 4px 5px;
  }

  .ring-card h3 {
    font-size: 10px;
  }

  .ring-card strong {
    font-size: 14px;
  }

  .health-score-hero {
    padding: 3px;
  }

  .score-number {
    font-size: 88px;
  }

  .score-label {
    font-size: 20px;
  }

  .score-status {
    font-size: 14px;
    padding: 6px 12px;
    margin-top: 5px;
  }

  .stats-grid-secondary {
    margin-top: 8px;
  }

  .stat-item {
    padding: 5px;
  }

  .value {
    font-size: 18px;
  }

  .meta-row,
  .row-head,
  .row-item {
    font-size: 11px;
  }
}

@media (max-width: 1100px) {
  .health-screen {
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }

  .screen-main {
    grid-template-columns: 1fr;
    height: auto;
  }

  .bottom-grid {
    grid-template-columns: 1fr;
  }

  .center-col {
    grid-template-rows: auto auto;
  }

  .hero-card {
    overflow: visible;
  }

  .ring-stage,
  .graph-stage {
    height: 520px;
  }
}

@media (max-width: 880px) {
  .corner-alarm {
    position: static;
    width: 100%;
    justify-content: center;
    margin-bottom: 10px;
  }

  .screen-header {
    grid-template-columns: 1fr;
    justify-items: center;
  }

  .header-nav,
  .header-nav-right {
    justify-content: center;
  }

  .ring-stage {
    gap: 4px;
  }

  .ring-card h3 {
    font-size: 8px;
  }

  .ring-card strong {
    font-size: 10px;
  }

  .hero-top {
    flex-direction: column;
    gap: 8px;
  }
}
</style>
