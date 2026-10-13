<template>
  <section class="radar-gat-page">
    <header class="gat-panel gat-header">
      <div>
        <p class="gat-eyebrow">DEDICATED RADAR TEMPORAL HEALTH</p>
        <h1>雷达多源时序健康评估</h1>
        <p class="gat-subtitle">{{ modelStatus?.model_label || 'GAT-5 + GRU + VAE' }} · 连续协议回放 · 当前帧重构误差</p>
      </div>
      <div class="gat-header-actions">
        <span class="gat-state" :class="modelReady ? 'is-online' : 'is-offline'">{{ modelReady ? '模型在线' : '模型未就绪' }}</span>
        <button class="gat-button" type="button" @click="router.push('/health')">返回健康页</button>
      </div>
    </header>

    <main class="gat-content">
      <section class="gat-panel live-panel">
        <div class="gat-section-head">
          <div>
            <p class="gat-eyebrow">LIVE REPLAY</p>
            <h2>实时协议回放评估</h2>
          </div>
          <span class="gat-state" :class="liveStateClass">{{ liveStateText }}</span>
        </div>
        <p class="gat-description">使用当前协议帧之前连续的 12 帧完整历史，评估当前帧重构误差；Socket 推送只在后台静默刷新，保留最近一次有效结果。</p>

        <div v-if="!liveEvaluation && evaluationLoading" class="gat-empty">正在连接实时协议回放…</div>
        <div v-else-if="!liveEvaluation && warmingUp" class="gat-empty">{{ warmingUp }}</div>
        <div v-else-if="!liveEvaluation && evaluationError" class="gat-empty is-error">{{ evaluationError }}</div>
        <div v-else-if="liveEvaluation" class="live-result">
          <div class="gat-metrics">
            <article class="gat-metric is-primary">
              <span>当前重构健康度</span>
              <strong>{{ liveEvaluation.overall_score }}</strong>
              <small>{{ liveEvaluation.overall_status }}</small>
            </article>
            <article class="gat-metric">
              <span>运行模型</span>
              <strong>{{ liveEvaluation.model_version }}</strong>
              <small>验证集选型</small>
            </article>
            <article class="gat-metric">
              <span>时序输入</span>
              <strong>{{ liveEvaluation.input.total_frames }} 帧</strong>
              <small>{{ liveEvaluation.input.history_frames }} 历史帧 + 当前帧 · {{ liveEvaluation.feature_count }} 参数</small>
            </article>
          </div>
          <div class="gat-source">
            <span>协议时间：{{ liveEvaluation.source?.timestamp || '—' }}</span>
            <span>回放序号：{{ liveEvaluation.source?.sequence ?? '—' }}</span>
            <span>最后成功更新：{{ lastLiveUpdate || '—' }}</span>
          </div>
          <div class="gat-score-list">
            <div v-for="item in liveEvaluation.subsystems.slice(0, 8)" :key="item.id" class="gat-score-row">
              <span>{{ item.name }}</span>
              <div class="gat-score-track"><i :class="scoreClass(item.score)" :style="{ width: `${item.score}%` }" /></div>
              <strong :class="scoreClass(item.score)">{{ item.score }}</strong>
            </div>
          </div>
          <p class="gat-note">{{ liveEvaluation.assessment_note }}</p>
        </div>
      </section>

      <section class="gat-panel demo-panel">
        <div class="gat-section-head">
          <div>
            <p class="gat-eyebrow">HELD-OUT TEST REPLAY</p>
            <h2>测试集动态重构演示</h2>
          </div>
          <div class="gat-controls">
            <button class="gat-button" type="button" :disabled="!demo?.points?.length" @click="togglePlayback">
              {{ playing ? '暂停' : '播放' }}
            </button>
            <button class="gat-button" type="button" :disabled="!demo?.points?.length" @click="resetPlayback">重置</button>
          </div>
        </div>
        <p class="gat-description">{{ demo?.model_label || '当前 GAT 模型' }} 与统计基线、加权距离、阈值投票、模糊综合、K-Means、SOM 对照。可训练方法仅用 7月19–24日训练；各方法按 7月25日验证集 P99 统一标定，再在 7月27日同一测试帧逐点比较。</p>

        <div v-if="demoError" class="gat-empty is-error">{{ demoError }}</div>
        <div v-else-if="!demoPoint" class="gat-empty">正在加载测试集回放…</div>
        <template v-else>
          <div class="gat-metrics">
            <article class="gat-metric is-primary">
              <span>当前重构健康度</span>
              <strong>{{ demoPoint.overall_score }}</strong>
              <small>{{ demoPoint.overall_status }}</small>
            </article>
            <article class="gat-metric">
              <span>选中模型</span>
              <strong>{{ demo.model }}</strong>
              <small>验证集优选</small>
            </article>
            <article class="gat-metric">
              <span>测试集回放位置</span>
              <strong>{{ demoIndex + 1 }} / {{ demo.points.length }}</strong>
              <small>{{ demoPoint.timestamp }}</small>
            </article>
          </div>
          <div class="gat-chart">
            <svg viewBox="0 0 1200 440" preserveAspectRatio="none" :aria-label="`${demo.model_label || 'GAT'} 与六种基线的测试集健康度曲线`">
              <g v-for="tick in chartTicks" :key="tick">
                <line :x1="chartLeft" :x2="chartRight" :y1="chartY(tick)" :y2="chartY(tick)" class="chart-grid" />
                <text :x="chartLeft - 12" :y="chartY(tick) + 5" class="chart-axis-label" text-anchor="end">{{ tick }}</text>
              </g>
              <line :x1="chartLeft" :y1="chartY(60)" :x2="chartRight" :y2="chartY(60)" class="chart-threshold" />
              <polyline
                v-for="line in demo.series || []"
                :key="line.key"
                :points="linePolyline(line)"
                class="chart-line"
                :class="{ 'is-gat': line.key === primarySeriesKey }"
                :style="{ stroke: line.color }"
              />
              <line v-if="demoPoint" :x1="demoCursorX" :x2="demoCursorX" :y1="chartY(100)" :y2="chartY(0)" class="chart-cursor" />
              <circle
                v-for="line in demo.series || []"
                :key="`${line.key}-cursor`"
                :cx="demoCursorX"
                :cy="chartY(line.points?.[demoIndex]?.overall_score)"
                :r="line.key === primarySeriesKey ? 6 : 4"
                class="chart-point"
                :style="{ fill: line.color }"
              />
              <line :x1="chartLeft" :x2="chartRight" :y1="chartY(0)" :y2="chartY(0)" class="chart-axis" />
              <text :x="chartLeft" y="426" class="chart-axis-label">{{ replayTime(demo.series?.[0]?.points?.[0]?.timestamp) }}</text>
              <text :x="chartRight" y="426" class="chart-axis-label" text-anchor="end">{{ replayTime(demo.series?.[0]?.points?.at(-1)?.timestamp) }}</text>
            </svg>
            <div class="chart-caption"><span>纵轴：健康度 0–100</span><span>虚线：正常阈值 60</span><span>游标：{{ demoPoint.timestamp }}</span></div>
            <div class="chart-legend">
              <div v-for="line in demo.series || []" :key="line.key">
                <i :style="{ backgroundColor: line.color }" />
                <span>{{ line.label }}</span>
                <strong>{{ line.points?.[demoIndex]?.overall_score ?? '—' }}</strong>
              </div>
            </div>
          </div>
          <section v-if="demo.openjev_decision?.ready" class="openjev-panel">
            <div class="gat-section-head openjev-head">
              <div>
                <p class="gat-eyebrow">SEMIF · DIRECT LOGIT · EXPLORATORY ONLY</p>
                <h3>开源 Jev 型模型：时序状态解释支持度</h3>
              </div>
              <div class="openjev-current">
                <span>本机快速候选 · 当前相对最支持</span>
                <strong>{{ demo.openjev_decision.model }}</strong>
                <small>{{ openJevSelectedLabel }} · {{ openJevSelectedValue }} / 100 · {{ demoPoint.timestamp }}</small>
              </div>
            </div>
            <p class="gat-description">{{ demo.openjev_decision.model }} · 本机单条 direct-logit 前向 P50 / P95：{{ demo.openjev_decision.local_forward_ms_median ?? '—' }} / {{ demo.openjev_decision.local_forward_ms_p95 ?? '—' }} ms；当前为离线预计算轨迹，桌面端仅回放、不内置模型权重；上下文使用变间隔真实时间戳。</p>
            <div class="openjev-chart">
              <svg viewBox="0 0 1200 290" preserveAspectRatio="none" aria-label="SemIf 直接选项打分对三种状态解释的相对支持度曲线">
                <g v-for="tick in openJevTicks" :key="tick">
                  <line :x1="chartLeft" :x2="chartRight" :y1="openJevY(tick)" :y2="openJevY(tick)" class="chart-grid" />
                  <text :x="chartLeft - 12" :y="openJevY(tick) + 5" class="chart-axis-label" text-anchor="end">{{ tick }}</text>
                </g>
                <polyline
                  v-for="label in demo.openjev_decision.labels"
                  :key="label.key"
                  :points="openJevPolyline(label.key)"
                  class="openjev-line"
                  :style="{ stroke: label.color }"
                />
                <line :x1="demoCursorX" :x2="demoCursorX" :y1="openJevY(100)" :y2="openJevY(0)" class="chart-cursor" />
                <circle
                  v-for="label in demo.openjev_decision.labels"
                  :key="`${label.key}-openjev-cursor`"
                  :cx="demoCursorX"
                  :cy="openJevY(openJevValue(demoPoint, label.key))"
                  r="5"
                  class="chart-point"
                  :style="{ fill: label.color }"
                />
                <line :x1="chartLeft" :x2="chartRight" :y1="openJevY(0)" :y2="openJevY(0)" class="chart-axis" />
                <text :x="chartLeft" y="276" class="chart-axis-label">{{ replayTime(demo.points[0]?.timestamp) }}</text>
                <text :x="chartRight" y="276" class="chart-axis-label" text-anchor="end">{{ replayTime(demo.points.at(-1)?.timestamp) }}</text>
              </svg>
              <div class="chart-caption"><span>纵轴：候选解释相对支持度 0–100</span><span>非健康分数、非故障概率</span><span>同步游标：{{ demoPoint.timestamp }}</span></div>
              <div class="chart-legend openjev-legend">
                <div v-for="label in demo.openjev_decision.labels" :key="label.key">
                  <i :style="{ backgroundColor: label.color }" />
                  <span>{{ label.label }}</span>
                  <strong>{{ openJevValue(demoPoint, label.key).toFixed(1) }}</strong>
                </div>
              </div>
            </div>
            <div class="comparison-table-wrap openjev-comparison-wrap">
              <h3>MiniCPM5-1B 本机速度与固定测试方案</h3>
              <p class="gat-description mttd-description">
                阈值只由验证集冻结；“健康点越阈”不是已知真值误报率，“合成事件检出”仅是人为持续偏移压力测试，不代表真实设备故障准确率。公开版不包含实测推理性能结论。
              </p>
              <table class="comparison-table openjev-comparison-table">
                <thead><tr><th>端侧运行模型</th><th>单条推理 P50 / P95</th><th>正常测试点越验证阈值</th><th>合成测试事件检出</th></tr></thead>
                <tbody><tr class="is-selected-openjev">
                    <td>{{ demo.openjev_decision.model }}</td>
                    <td>{{ demo.openjev_decision.local_forward_ms_median ?? '—' }} / {{ demo.openjev_decision.local_forward_ms_p95 ?? '—' }} ms</td>
                    <td>{{ demo.openjev_decision.test_normal_above_threshold_count ?? '—' }} / {{ demo.openjev_decision.test_normal_count ?? '—' }}（{{ percent(demo.openjev_decision.test_normal_above_threshold_rate) }}）</td>
                    <td>{{ demo.openjev_decision.synthetic_detected_event_count ?? '—' }} / {{ demo.openjev_decision.synthetic_event_count ?? '—' }}（{{ percent(demo.openjev_decision.synthetic_event_detection_rate) }}）</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="gat-note openjev-caveat">{{ demo.openjev_decision.note }} {{ demo.openjev_decision.prompt_mode_label }}。测试集只有正常协议回放，未包含物理故障真值；曲线只是候选解释比较，不证明该模型具备雷达故障检测能力。具体实验口径见本地报告。</p>
          </section>
          <p class="gat-note comparison-caveat">
            本对照仅评价正常回放上的分数稳定性与低分告警倾向。27日数据没有物理故障标签，因此不能据此断言故障检出率或普遍算法优劣；当前运行模型曲线加粗显示。
          </p>
          <div class="comparison-table-wrap">
            <h3>测试集汇总（同一批有效时序帧）</h3>
            <table class="comparison-table">
              <thead><tr><th>方法</th><th>平均健康度</th><th>P05</th><th>低于60点数 / 比例</th><th>低于30点数 / 比例</th></tr></thead>
              <tbody>
                <tr v-for="item in demo.comparison_summary || []" :key="item.key" :class="{ 'is-gat-row': item.key === primarySeriesKey }">
                  <td>{{ item.label }}</td>
                  <td>{{ item.mean_health }}</td>
                  <td>{{ item.p05_health }}</td>
                  <td>{{ item.below_60_count }} / {{ percent(item.below_60_rate) }}</td>
                  <td>{{ item.below_30_count }} / {{ percent(item.below_30_rate) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-if="depthMttdRows.length" class="comparison-table-wrap depth-mttd-wrap">
            <h3>GAT 层数与 MTTD 对比（{{ depthMttdRows.length }} 个深度）</h3>
            <p class="gat-description mttd-description">
              阈值由验证集正常段 P99 冻结；在验证/测试回放副本上注入单参数持续阶跃，连续 2 帧超阈才算检出。这里是合成故障 MTTD，不代表真实现场故障延迟；测试结果仅展示，不参与当前层数选择。
            </p>
            <table class="comparison-table depth-mttd-table">
              <thead><tr><th>GAT 深度</th><th>验证检出率</th><th>验证 MTTD 中位数 / P95</th><th>测试检出率</th><th>测试 MTTD 中位数 / P95</th><th>测试未检出</th><th>正常测试超阈点率</th><th>CPU推理 P95</th></tr></thead>
              <tbody>
                <tr v-for="item in depthMttdRows" :key="item.key" :class="{ 'is-selected-depth': item.depth === selectedDepth, 'is-deployed-depth': item.depth === deployedDepth }">
                  <td>{{ item.label }}<small v-if="item.depth === deployedDepth">当前部署</small></td>
                  <td>{{ detectionCell(item.val_events) }}</td>
                  <td>{{ delayPair(item.val_events) }}</td>
                  <td>{{ detectionCell(item.test_events) }}</td>
                  <td>{{ delayPair(item.test_events) }}</td>
                  <td>{{ item.test_events.missed_event_count }} / {{ item.test_events.event_count }}</td>
                  <td>{{ percent(item.test_normal.alarm_point_rate) }}</td>
                  <td>{{ item.cpu_single_frame_inference.p95_ms }} ms</td>
                </tr>
              </tbody>
            </table>
            <p class="mttd-selection-note">此处层数注入评估按 {{ demo.depth_mttd?.model_selection?.selected_by || '验证集目标函数' }}，是单独的 VAE 层数参考；“当前部署”标记本页实际运行模型的层数。7月27日正常测试段超阈点率偏高，显示跨日阈值迁移存在误报风险，因此合成故障检出率不能单独代表方法优劣。</p>
          </div>
          <div v-if="modelSelectionRows.length" class="comparison-table-wrap model-selection-wrap">
            <h3>候选模型选型依据（{{ modelSelectionRows.length }} 种结构）</h3>
            <p class="gat-description mttd-description">
              {{ demo.model_selection.selection_rule }} 当前部署：{{ demo.model_selection.current_deployed_model_label }}；候选按验证集三随机种子均值排序。测试 MSE 仅作最终诊断，不参与选型；数据均为健康回放，不能解释成真实故障检出能力。
            </p>
            <table class="comparison-table model-selection-table">
              <thead><tr><th>候选结构</th><th>验证 MSE 均值 ± SD</th><th>测试 MSE 均值 ± SD（诊断）</th><th>随机种子</th></tr></thead>
              <tbody>
                <tr v-for="item in modelSelectionRows" :key="item.key" :class="{ 'is-selected-model': item.key === selectedCandidateKey, 'is-deployed-model': item.label === demo.model_selection.current_deployed_model_label }">
                  <td>{{ item.label }}<small v-if="item.key === selectedCandidateKey">验证集均值最优</small><small v-if="item.label === demo.model_selection.current_deployed_model_label">当前部署</small></td>
                  <td>{{ msePair(item.validation_mse_mean, item.validation_mse_std_sample) }}</td>
                  <td>{{ msePair(item.test_mse_mean, item.test_mse_std_sample) }}</td>
                  <td>{{ item.seed_count }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="gat-note">
            {{ demo.parameter_label }}：实际 {{ demoPoint.actual_normalized }} · 重构 {{ demoPoint.reconstructed_normalized }} · 误差 {{ demoPoint.reconstruction_error }}
          </div>
          <div class="gat-score-list">
            <div v-for="item in demoPoint.subsystems" :key="item.id" class="gat-score-row">
              <span>{{ item.id }} {{ item.name }}</span>
              <div class="gat-score-track"><i :class="scoreClass(item.score)" :style="{ width: `${item.score}%` }" /></div>
              <strong :class="scoreClass(item.score)">{{ item.score }}</strong>
            </div>
          </div>
        </template>
      </section>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { API_PREFIX } from '../config/backend'
import { createDashboardSocket } from '../socket/dashboardSocket'

const router = useRouter()
const modelStatus = ref(null)
const evaluationLoading = ref(true)
const liveEvaluation = ref(null)
const evaluationError = ref('')
const warmingUp = ref('')
const lastLiveUpdate = ref('')
const demo = ref(null)
const demoError = ref('')
const demoIndex = ref(0)
const playing = ref(false)
let evaluationInFlight = false
let refreshTimer = null
let playbackTimer = null
let dashboardSocket = null

const modelReady = computed(() => Boolean(modelStatus.value?.ready))
const liveStateText = computed(() => {
  if (liveEvaluation.value) return '在线'
  if (warmingUp.value) return '积累窗口'
  if (evaluationError.value) return '异常'
  return evaluationLoading.value ? '连接中' : '等待数据'
})
const liveStateClass = computed(() => liveEvaluation.value ? 'is-online' : (evaluationError.value ? 'is-offline' : 'is-pending'))
const demoPoint = computed(() => demo.value?.points?.[demoIndex.value] || null)
const primarySeriesKey = computed(() => demo.value?.primary_series_key || 'gat5_vae')
const openJevSelectedLabel = computed(() => demoPoint.value?.openjev_decision?.selected_label || '—')
const openJevSelectedValue = computed(() => Number(demoPoint.value?.openjev_decision?.support_percent?.[demoPoint.value?.openjev_decision?.selected] ?? 0).toFixed(1))
const modelSelectionRows = computed(() => demo.value?.model_selection?.candidates || [])
const selectedCandidateKey = computed(() => demo.value?.model_selection?.selected_candidate_key || '')
const depthMttdRows = computed(() => Object.entries(demo.value?.depth_mttd?.models || {})
  .map(([key, item]) => ({ key, label: `GAT-${item.depth}`, ...item }))
  .sort((left, right) => left.depth - right.depth))
const depthNumber = (value) => Number(String(value || '').match(/\d+/)?.[0] || 0)
const selectedDepth = computed(() => depthNumber(demo.value?.depth_mttd?.model_selection?.selected_depth))
const deployedDepth = computed(() => depthNumber(demo.value?.model))
const chartLeft = 76
const chartRight = 1184
const chartTop = 24
const chartBottom = 360
const chartTicks = [100, 80, 60, 40, 20, 0]
const chartY = (score) => chartBottom - (Math.max(0, Math.min(100, Number(score ?? 0))) / 100) * (chartBottom - chartTop)
const openJevTicks = [100, 75, 50, 25, 0]
const openJevY = (score) => 232 - (Math.max(0, Math.min(100, Number(score ?? 0))) / 100) * 196
const demoCursorX = computed(() => {
  const count = demo.value?.points?.length || 1
  return chartLeft + (demoIndex.value / Math.max(1, count - 1)) * (chartRight - chartLeft)
})
const replayTime = (timestamp) => String(timestamp || '').replace(/^\d{4}[/-]/, '')
const linePolyline = (line) => {
  const points = line?.points?.slice(0, demoIndex.value + 1) || []
  if (points.length < 2) return ''
  return points.map((point, index) => {
    const x = chartLeft + (index / (line.points.length - 1)) * (chartRight - chartLeft)
    const y = chartY(point.overall_score)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}
const openJevValue = (point, key) => Number(point?.openjev_decision?.support_percent?.[key] ?? 0)
const openJevPolyline = (key) => {
  const points = demo.value?.points?.slice(0, demoIndex.value + 1) || []
  if (points.length < 2) return ''
  return points.map((point, index) => {
    const x = chartLeft + (index / (demo.value.points.length - 1)) * (chartRight - chartLeft)
    return `${x.toFixed(1)},${openJevY(openJevValue(point, key)).toFixed(1)}`
  }).join(' ')
}

const percent = (value) => `${(Number(value || 0) * 100).toFixed(2)}%`
const msePair = (mean, deviation) => `${Number(mean).toFixed(6)} ± ${Number(deviation).toFixed(6)}`
const delayPair = (metrics) => {
  const median = metrics?.mttd_median_seconds
  const p95 = metrics?.mttd_p95_seconds
  if (median == null || p95 == null) return '未检出'
  return `${Number(median).toFixed(1)} / ${Number(p95).toFixed(1)} s`
}
const detectionCell = (metrics) => `${percent(metrics?.detection_rate)} (${metrics?.detected_count ?? 0}/${metrics?.event_count ?? 0})`

const scoreClass = (score) => {
  const value = Number(score)
  if (value >= 60) return 'score-good'
  if (value >= 30) return 'score-warn'
  return 'score-danger'
}

const loadLiveEvaluation = async ({ initial = false } = {}) => {
  if (evaluationInFlight) return
  evaluationInFlight = true
  if (initial && !liveEvaluation.value) evaluationLoading.value = true
  try {
    const response = await axios.get(`${API_PREFIX}/health/reconstruction/evaluate`)
    const payload = response.data || {}
    if (payload.warming_up) {
      if (!liveEvaluation.value) warmingUp.value = payload.warming_up
      return
    }
    if (payload.data) {
      liveEvaluation.value = payload.data
      warmingUp.value = ''
      evaluationError.value = ''
      lastLiveUpdate.value = new Date().toLocaleString('zh-CN')
    }
  } catch (error) {
    if (!liveEvaluation.value) {
      evaluationError.value = error.response?.data?.error || '实时重构评估暂不可用。'
    }
  } finally {
    evaluationLoading.value = false
    evaluationInFlight = false
  }
}

const loadPageData = async () => {
  const [statusResult, demoResult] = await Promise.allSettled([
    axios.get(`${API_PREFIX}/health/reconstruction/status`),
    axios.get(`${API_PREFIX}/health/reconstruction/demo`, { params: { split: 'test', limit: 180 } })
  ])
  if (statusResult.status === 'fulfilled') modelStatus.value = statusResult.value.data?.data || null
  if (statusResult.status === 'rejected') modelStatus.value = null
  if (demoResult.status === 'fulfilled') demo.value = demoResult.value.data?.data || null
  if (demoResult.status === 'rejected') demoError.value = demoResult.reason.response?.data?.error || '测试集演示暂不可用。'
}

const resetPlayback = () => {
  demoIndex.value = 0
  playing.value = false
  if (playbackTimer) window.clearInterval(playbackTimer)
  playbackTimer = null
}

const togglePlayback = () => {
  if (!demo.value?.points?.length) return
  if (playing.value) {
    playing.value = false
    if (playbackTimer) window.clearInterval(playbackTimer)
    playbackTimer = null
    return
  }
  playing.value = true
  playbackTimer = window.setInterval(() => {
    if (!demo.value?.points?.length) return
    demoIndex.value = demoIndex.value >= demo.value.points.length - 1 ? 0 : demoIndex.value + 1
  }, 180)
}

onMounted(async () => {
  await Promise.all([loadPageData(), loadLiveEvaluation({ initial: true })])
  dashboardSocket = createDashboardSocket({
    onDashboardUpdate: () => {
      if (refreshTimer) window.clearTimeout(refreshTimer)
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null
        loadLiveEvaluation()
      }, 250)
    }
  })
})

onUnmounted(() => {
  if (refreshTimer) window.clearTimeout(refreshTimer)
  if (playbackTimer) window.clearInterval(playbackTimer)
  dashboardSocket?.disconnect()
  dashboardSocket = null
})
</script>

<style scoped>
.radar-gat-page {
  min-height: calc(100vh - 24px);
  padding: 14px;
  color: #d7f3ff;
  border: 2px solid #18bfff;
  border-radius: 12px;
  background: radial-gradient(circle at 18% 0%, rgba(66, 166, 255, 0.17), transparent 38%), linear-gradient(180deg, #05153d 0%, #07255f 48%, #06194b 100%);
  box-shadow: inset 0 0 35px rgba(23, 125, 220, 0.2), 0 0 16px rgba(24, 190, 255, 0.2);
}
.gat-panel {
  border: 1px solid rgba(87, 201, 255, 0.38);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 37, 92, 0.9), rgba(6, 24, 67, 0.92));
  box-shadow: inset 0 0 16px rgba(34, 154, 255, 0.14);
}
.gat-header, .gat-section-head { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.gat-header { padding: 16px 18px; }
.gat-eyebrow { margin: 0 0 5px; color: #86dfff; font-size: 11px; letter-spacing: 1.6px; }
h1, h2 { margin: 0; color: #f2fbff; }
h1 { font-size: 27px; }
h2 { font-size: 19px; }
.gat-subtitle, .gat-description { color: #9edff4; font-size: 12px; line-height: 1.55; }
.gat-subtitle { margin: 6px 0 0; }
.gat-header-actions, .gat-controls { display: flex; align-items: center; gap: 9px; }
.gat-state { display: inline-flex; align-items: center; gap: 7px; padding: 6px 10px; border: 1px solid rgba(255,255,255,.15); border-radius: 999px; font-size: 12px; white-space: nowrap; }
.gat-state::before { width: 7px; height: 7px; content: ''; border-radius: 50%; background: currentColor; }
.gat-state.is-online { color: #58e7b0; border-color: rgba(88,231,176,.38); background: rgba(22,130,99,.14); }
.gat-state.is-offline { color: #ff8390; border-color: rgba(255,131,144,.38); background: rgba(139,34,51,.14); }
.gat-state.is-pending { color: #ffd365; border-color: rgba(255,211,101,.38); background: rgba(139,102,34,.14); }
.gat-button { padding: 7px 12px; border: 1px solid rgba(87,201,255,.5); border-radius: 6px; color: #b9ecff; background: rgba(8,46,104,.9); cursor: pointer; font: inherit; font-size: 12px; }
.gat-button:hover:not(:disabled) { border-color: #70ddff; background: rgba(18,70,145,.92); }
.gat-button:disabled { cursor: not-allowed; opacity: .48; }
.gat-content { display: grid; grid-template-columns: minmax(0, 1fr); gap: 12px; margin-top: 12px; }
.live-panel, .demo-panel { min-width: 0; padding: 14px; }
.gat-section-head { margin-bottom: 8px; }
.gat-description { margin: 7px 0 12px; }
.gat-empty { padding: 18px; border: 1px dashed rgba(120,205,255,.28); border-radius: 8px; color: #9edff4; background: rgba(4,20,53,.42); font-size: 13px; }
.gat-empty.is-error { color: #ff9ca5; border-color: rgba(255,131,144,.4); }
.gat-metrics { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.gat-metric { display: flex; min-width: 0; min-height: 94px; flex-direction: column; justify-content: center; padding: 12px; border: 1px solid rgba(96,205,255,.25); border-radius: 8px; background: rgba(4,20,53,.5); }
.gat-metric.is-primary { border-color: rgba(86,255,192,.38); background: linear-gradient(135deg, rgba(8,82,78,.46), rgba(4,30,67,.65)); }
.gat-metric span, .gat-metric small { color: #9edff4; font-size: 11px; }
.gat-metric strong { margin: 4px 0; overflow-wrap: anywhere; color: #f2fbff; font-size: 22px; }
.gat-metric small { line-height: 1.45; }
.gat-source { display: flex; flex-wrap: wrap; gap: 8px 18px; margin: 10px 1px; color: #8bcfe8; font-size: 11px; }
.gat-score-list { display: grid; gap: 7px; }
.gat-score-row { display: grid; grid-template-columns: minmax(130px, 1fr) minmax(100px, 2fr) 42px; align-items: center; gap: 10px; font-size: 12px; }
.gat-score-row > span { overflow: hidden; color: #c4e9f7; text-overflow: ellipsis; white-space: nowrap; }
.gat-score-track { height: 7px; overflow: hidden; border-radius: 999px; background: rgba(142,190,220,.16); }
.gat-score-track i { display: block; height: 100%; border-radius: inherit; }
.score-good { color: #52e6ad; background-color: #52e6ad; }
.score-warn { color: #ffd365; background-color: #ffd365; }
.score-danger { color: #ff687b; background-color: #ff687b; }
.gat-note { margin: 10px 0 0; padding: 9px 10px; border-radius: 6px; color: #b9eafb; background: rgba(4,20,53,.46); font-size: 11px; line-height: 1.55; }
.gat-chart { margin: 10px 0; padding: 8px; border: 1px solid rgba(107,215,255,.2); border-radius: 7px; background: rgba(4,20,53,.62); }
.gat-chart svg { display: block; width: 100%; height: clamp(520px, 60vh, 720px); }
.openjev-panel { margin-top: 18px; padding: 14px; border: 1px solid rgba(181,145,255,.42); border-radius: 9px; background: linear-gradient(145deg, rgba(29,22,75,.72), rgba(4,20,53,.62)); }
.openjev-head { align-items: flex-start; }
.openjev-head h3 { margin: 0; color: #f3edff; font-size: 17px; }
.openjev-current { display: flex; min-width: 220px; flex-direction: column; align-items: flex-end; gap: 3px; text-align: right; }
.openjev-current span, .openjev-current small { color: #c0b2e8; font-size: 11px; }
.openjev-current strong { color: #fff; font-size: 19px; }
.openjev-chart { padding: 8px; border: 1px solid rgba(181,145,255,.2); border-radius: 7px; background: rgba(8,9,36,.54); }
.openjev-chart svg { display: block; width: 100%; height: clamp(260px, 32vh, 360px); }
.openjev-line { fill: none; stroke-width: 4; stroke-linejoin: round; stroke-linecap: round; opacity: .92; }
.openjev-legend > div { grid-template-columns: 12px minmax(0, 1fr) 56px; }
.openjev-legend strong { color: #f5edff; }
.openjev-caveat { border: 1px solid rgba(181,145,255,.27); color: #ded2ff; }
.chart-grid { stroke: rgba(129,194,225,.18); stroke-width: 1; }
.chart-axis { stroke: rgba(164,220,245,.56); stroke-width: 1.2; }
.chart-axis-label { fill: #9acfe5; font-size: 17px; }
.chart-line { fill: none; stroke-width: 3.2; stroke-linejoin: round; stroke-linecap: round; opacity: .9; }
.chart-line.is-gat { stroke-width: 5.4; opacity: 1; }
.chart-threshold { stroke: rgba(255,226,122,.9); stroke-width: 2.6; stroke-dasharray: 12 9; }
.chart-cursor { stroke: rgba(255,255,255,.82); stroke-width: 2; stroke-dasharray: 5 6; }
.chart-point { stroke: #06194b; stroke-width: 2.5; }
.chart-caption { display: flex; justify-content: space-between; gap: 8px; color: #8bcfe8; font-size: 13px; }
.chart-legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 8px 14px; margin-top: 12px; }
.chart-legend > div { display: grid; grid-template-columns: 12px minmax(0, 1fr) 42px; align-items: center; gap: 9px; color: #b9eafb; font-size: 13px; }
.chart-legend i { width: 11px; height: 11px; border-radius: 50%; }
.chart-legend strong { text-align: right; color: #f2fbff; }
.comparison-caveat { border: 1px solid rgba(255,211,101,.24); }
.comparison-table-wrap { margin-top: 12px; overflow-x: auto; }
.comparison-table-wrap h3 { margin: 0 0 8px; color: #e4f8ff; font-size: 14px; }
.comparison-table { width: 100%; border-collapse: collapse; color: #c4e9f7; font-size: 11px; text-align: left; }
.comparison-table th, .comparison-table td { padding: 8px 9px; border-bottom: 1px solid rgba(107,215,255,.15); white-space: nowrap; }
.comparison-table th { color: #8bcfe8; font-weight: 600; }
.comparison-table .is-gat-row { color: #67efba; background: rgba(24,152,117,.1); }
.model-selection-wrap { padding: 12px; border: 1px solid rgba(107,215,255,.22); border-radius: 8px; background: rgba(4,20,53,.35); }
.model-selection-table { min-width: 760px; }
.model-selection-table td:first-child { font-weight: 700; }
.model-selection-table td small { display: inline-block; margin-left: 7px; color: #75ecc0; font-size: 9px; }
.model-selection-table .is-selected-model { color: #67efba; background: rgba(24,152,117,.1); }
.model-selection-table .is-deployed-model { box-shadow: inset 3px 0 #56ffc0; }
.openjev-comparison-wrap { padding: 12px; border: 1px solid rgba(181,145,255,.2); border-radius: 8px; background: rgba(4,20,53,.35); }
.openjev-comparison-table { min-width: 760px; }
.openjev-comparison-table td:first-child { font-weight: 700; }
.openjev-comparison-table td small { display: inline-block; margin-left: 7px; color: #75ecc0; font-size: 9px; }
.openjev-comparison-table .is-selected-openjev { color: #e0d4ff; background: rgba(128,94,210,.13); box-shadow: inset 3px 0 #b99aff; }
.depth-mttd-wrap { padding: 12px; border: 1px solid rgba(107,215,255,.22); border-radius: 8px; background: rgba(4,20,53,.35); }
.mttd-description { max-width: 1100px; margin: 4px 0 8px; }
.depth-mttd-table { min-width: 1060px; }
.depth-mttd-table td:first-child { font-weight: 700; }
.depth-mttd-table td small { display: block; margin-top: 3px; color: #75ecc0; font-size: 9px; }
.depth-mttd-table .is-selected-depth { background: rgba(255,211,101,.08); }
.depth-mttd-table .is-deployed-depth { color: #67efba; box-shadow: inset 3px 0 #56ffc0; }
.mttd-selection-note { margin: 8px 0 0; color: #8bcfe8; font-size: 10px; }
@media (max-width: 760px) {
  .gat-header, .gat-section-head { align-items: flex-start; flex-direction: column; }
  .openjev-current { align-items: flex-start; text-align: left; }
  .gat-header-actions { width: 100%; justify-content: space-between; }
  .gat-metrics { grid-template-columns: 1fr; }
  .gat-score-row { grid-template-columns: minmax(90px, 1fr) minmax(70px, 1.3fr) 35px; gap: 7px; }
  .chart-caption { flex-wrap: wrap; font-size: 10px; }
  .gat-chart svg { height: 360px; }
  .openjev-chart svg { height: 230px; }
  .chart-axis-label { font-size: 19px; }
}
</style>
