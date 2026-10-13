<template>
  <section class="algo-screen">
    <header class="screen-header panel">
      <div>
        <p class="eyebrow">HEALTH ALGORITHM CENTER</p>
        <h1>健康算法中心</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">模型输入：合成演示快照快照</span>
        <el-button class="action-btn ghost" @click="customDialogVisible = true">自定义算法</el-button>
        <el-button class="action-btn ghost" @click="goBack">返回健康页</el-button>
        <el-button class="action-btn ghost" @click="router.push('/radar-reconstruction')">时序健康专页</el-button>
        <el-button class="action-btn ghost" :loading="retrainLoading" :disabled="selectedAlgorithm.key === 'gat_vae_reconstruction'" @click="handleRetrain">重训基础模型</el-button>
      </div>
    </header>

    <div class="screen-grid">
      <article class="panel sidebar">
        <h2>算法目录</h2>

        <section v-for="group in algorithmGroups" :key="group.key" class="group-block">
          <h3>{{ group.title }}</h3>
          <div class="algo-list">
            <button
              v-for="item in group.algorithms"
              :key="item.key"
              type="button"
              class="algo-card"
              :class="{ active: selectedAlgorithm.key === item.key }"
              @click="selectAlgorithm(item)"
            >
              <strong>
                {{ item.name }}
                <em v-if="item.implemented" class="implemented-tag">已实装</em>
              </strong>
            </button>
          </div>
        </section>
      </article>

      <article class="panel workspace">
        <div class="workspace-head">
          <p class="group-name">{{ selectedAlgorithm.groupTitle }}</p>
          <h2>{{ selectedAlgorithm.name }}界面</h2>
        </div>

        <section class="runtime-box">
          <div class="runtime-head">
            <div>
              <h4>实时运行结果</h4>
              <p>{{ runtimeDescription }}</p>
            </div>
            <span class="runtime-badge" :class="runtimeBadgeClass">{{ runtimeBadgeText }}</span>
          </div>

          <div v-if="runtimeLoading" class="runtime-empty">正在读取当前快照并运行模型…</div>
          <div v-else-if="runtimeWaitingMessage" class="runtime-empty">{{ runtimeWaitingMessage }}</div>
          <div v-else-if="runtimeError" class="runtime-empty error-text">{{ runtimeError }}</div>

          <template v-else-if="isAssessmentAlgorithm && evaluation">
            <div class="metric-grid">
              <div class="metric-card primary-metric">
                <span>模型健康度</span>
                <strong>{{ evaluation.overall_score }}</strong>
                <small>{{ evaluation.overall_status }}</small>
              </div>
              <div class="metric-card">
                <span>{{ evaluation.model_version ? '时序模型版本' : '识别置信度' }}</span>
                <strong>{{ evaluation.model_version || (evaluation.confidence == null ? '—' : percent(evaluation.confidence)) }}</strong>
                <small>{{ evaluation.model_version ? '验证集选型' : (evaluation.cluster == null ? '规则基线' : `状态簇 ${evaluation.cluster + 1}`) }}</small>
              </div>
              <div class="metric-card">
                <span>模型输入</span>
                <strong>{{ evaluation.feature_count }}</strong>
                <small>维参数特征</small>
              </div>
            </div>
            <div class="subsystem-score-list">
              <div v-for="item in evaluation.subsystems.slice(0, 8)" :key="item.id" class="subsystem-score-row">
                <span>{{ item.name }}</span>
                <div class="score-track"><i :style="{ width: `${item.score}%` }" /></div>
                <strong :class="scoreClass(item.score)">{{ item.score }}</strong>
              </div>
            </div>
          </template>

          <template v-else-if="isPredictionAlgorithm && prediction">
            <div class="metric-grid prediction-metrics">
              <div class="metric-card primary-metric">
                <span>预计剩余寿命</span>
                <strong>{{ prediction.remaining_life_hours }}</strong>
                <small>小时（演示模型）</small>
              </div>
              <div class="metric-card">
                <span>时间窗口</span>
                <strong>{{ prediction.input.window_size }}</strong>
                <small>× {{ prediction.input.feature_count }} 维</small>
              </div>
              <div class="metric-card">
                <span>预测跨度</span>
                <strong>{{ prediction.horizon }}</strong>
                <small>个未来时间点</small>
              </div>
            </div>
            <div class="forecast-list">
              <div v-for="item in prediction.forecast" :key="item.step" class="forecast-card">
                <div>
                  <span>{{ item.label }}</span>
                  <small>{{ item.overall_status }}</small>
                </div>
                <strong :class="scoreClass(item.overall_score)">{{ item.overall_score }}</strong>
              </div>
            </div>
          </template>

          <template v-else-if="isProcessingAlgorithm && processing">
            <div class="metric-grid">
              <div class="metric-card primary-metric"><span>处理维度</span><strong>{{ processing.processed_dimension }}</strong><small>维健康特征</small></div>
              <div class="metric-card"><span>分解模态</span><strong>{{ processing.mode_count }}</strong><small>个模态</small></div>
              <div class="metric-card"><span>平均健康特征</span><strong>{{ processing.mean_health_feature }}</strong><small>0–1</small></div>
            </div>
            <div class="subsystem-score-list"><div v-for="(value, index) in processing.energy" :key="index" class="subsystem-score-row"><span>模态 {{ index + 1 }} 能量</span><div class="score-track"><i :style="{ width: `${Math.min(100, value * 100)}%` }" /></div><strong>{{ value }}</strong></div></div>
          </template>

          <div v-else class="runtime-empty">正在等待当前算法结果。</div>
        </section>

        <section v-if="isGatAlgorithm" class="gat-demo-box">
          <div class="gat-demo-head">
            <div>
              <p class="group-name">HELD-OUT TEST REPLAY</p>
              <h3>测试集动态重构演示</h3>
            </div>
            <div class="gat-demo-controls">
              <el-button size="small" :disabled="!gatDemo?.points?.length" @click="toggleGatDemoPlayback">{{ gatDemoPlaying ? '暂停' : '播放' }}</el-button>
              <el-button size="small" :disabled="!gatDemo?.points?.length" @click="resetGatDemoPlayback">重置</el-button>
            </div>
          </div>
          <p class="gat-demo-caption">留出测试集回放（2026-07-27），不参与训练或模型选型；播放时逐帧展示重构健康度和子系统误差。</p>
          <div v-if="gatDemoLoading" class="runtime-empty">正在加载测试集回放…</div>
          <div v-else-if="gatDemoError" class="runtime-empty error-text">{{ gatDemoError }}</div>
          <template v-else-if="gatDemoPoint">
            <div class="metric-grid gat-demo-metrics">
              <div class="metric-card primary-metric"><span>当前重构健康度</span><strong>{{ gatDemoPoint.overall_score }}</strong><small>{{ gatDemoPoint.overall_status }}</small></div>
              <div class="metric-card"><span>演示模型</span><strong>{{ gatDemo.model }}</strong><small>验证集选出的 GAT-5</small></div>
              <div class="metric-card"><span>测试回放位置</span><strong>{{ gatDemoIndex + 1 }} / {{ gatDemo.points.length }}</strong><small>{{ gatDemoPoint.timestamp }}</small></div>
            </div>
            <div class="gat-demo-chart">
              <svg viewBox="0 0 640 160" preserveAspectRatio="none" aria-label="测试集重构健康度动态曲线">
                <line x1="0" y1="66" x2="640" y2="66" class="gat-demo-threshold" />
                <polyline :points="gatDemoPolyline" class="gat-demo-line" />
                <line :x1="gatDemoCursorX" y1="8" :x2="gatDemoCursorX" y2="150" class="gat-demo-cursor" />
                <circle :cx="gatDemoCursorX" :cy="gatDemoCursorY" r="5" class="gat-demo-marker" />
              </svg>
              <div class="gat-demo-chart-caption"><span>健康度 100</span><span>阈值 60</span><span>当前：{{ gatDemoPoint.timestamp }}</span></div>
            </div>
            <div class="gat-demo-readout">{{ gatDemo.parameter_label }}：实际 {{ gatDemoPoint.actual_normalized }} · 重构 {{ gatDemoPoint.reconstructed_normalized }} · 误差 {{ gatDemoPoint.reconstruction_error }}</div>
            <input class="gat-demo-range" type="range" min="0" :max="Math.max(0, gatDemo.points.length - 1)" :value="gatDemoIndex" aria-label="测试集回放帧位置" @input="seekGatDemo($event)" />
            <div class="subsystem-score-list gat-demo-score-list">
              <div v-for="item in gatDemoPoint.subsystems" :key="item.id" class="subsystem-score-row">
                <span>{{ item.id }} {{ item.name }}</span>
                <div class="score-track"><i :class="scoreClass(item.score)" :style="{ width: `${item.score}%` }" /></div>
                <strong :class="scoreClass(item.score)">{{ item.score }}</strong>
              </div>
            </div>
          </template>
        </section>

        <section class="status-box">
          <div class="status-item">
            <span>当前算法</span>
            <strong>{{ selectedAlgorithm.name }}</strong>
          </div>
          <div class="status-item">
            <span>更新时间</span>
            <strong>{{ lastUpdatedText }}</strong>
          </div>
          <div class="status-item">
            <span>状态</span>
            <strong :class="modelReady ? 'online' : 'offline'">{{ modelStatusLabel }}</strong>
          </div>
        </section>

        <section v-if="selectedAlgorithm" class="hyperparam-box">
          <div class="runtime-head"><div><h4>超参数配置</h4><p>参数由后端定义并在运行时校验。</p></div><el-button v-if="currentParams.length" size="small" :loading="configSaving" @click="saveConfig">保存参数</el-button></div>
          <div v-if="currentParams.length" class="hyperparam-list"><label v-for="item in currentParams" :key="item.key"><span>{{ item.label }}</span><input v-model.number="item.value" :type="item.type || 'text'" :min="item.min" :max="item.max" :step="item.step || 1" /><small>{{ item.min }} – {{ item.max }}</small><em>已实装</em></label></div>
          <div v-else class="runtime-empty">该算法暂未接入可配置超参数。</div>
        </section>
      </article>
    </div>

    <el-dialog v-model="customDialogVisible" title="登记自定义算法" width="520px">
      <el-form label-width="130px"><el-form-item label="算法名称"><el-input v-model="customForm.name" /></el-form-item><el-form-item label="算法类别"><el-select v-model="customForm.category" style="width:100%"><el-option label="数据处理算法" value="数据处理算法" /><el-option label="健康评估算法" value="健康评估算法" /><el-option label="健康预测算法" value="健康预测算法" /></el-select></el-form-item><el-form-item label="算法文件路径"><el-input v-model="customForm.file_path" placeholder="/path/to/algorithm.py" /></el-form-item><el-form-item label="配置参数路径"><el-input v-model="customForm.config_path" placeholder="/path/to/config.json" /></el-form-item></el-form>
      <template #footer><el-button @click="customDialogVisible=false">取消</el-button><el-button type="primary" :loading="customSaving" @click="saveCustomAlgorithm">保存登记</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_PREFIX } from '../config/backend'
import { createDashboardSocket } from '../socket/dashboardSocket'

const router = useRouter()
const retrainLoading = ref(false)
const runtimeLoading = ref(false)
const runtimeError = ref('')
const runtimeWaitingMessage = ref('')
const modelStatus = ref(null)
const evaluation = ref(null)
const prediction = ref(null)
const processing = ref(null)
const lastUpdatedText = ref('--')
const currentParams = ref([])
const configSaving = ref(false)
const customDialogVisible = ref(false)
const customSaving = ref(false)
const customForm = ref({ name: '', category: '健康评估算法', file_path: '', config_path: '' })
let dashboardSocket = null
let refreshTimer = null
let runtimeRequestId = 0
let runtimeRefreshInFlight = false

const categoryTitles = {
  '数据处理算法': '数据信号处理算法',
  '健康评估算法': '健康诊断评估算法（自适应监测）',
  '健康预测算法': '健康预测算法（时间窗口）'
}
const categoryKeys = {
  '数据处理算法': 'signal-processing',
  '健康评估算法': 'diagnosis-assessment',
  '健康预测算法': 'health-prediction'
}
const algorithmGroups = ref([])
const allAlgorithms = computed(() => algorithmGroups.value.flatMap((group) => group.algorithms))
const selectedAlgorithmKey = ref('kmeans')

const selectedAlgorithm = computed(
  () => allAlgorithms.value.find((item) => item.key === selectedAlgorithmKey.value) || allAlgorithms.value[0] || { key: '', name: '算法', groupTitle: '' }
)

const isAssessmentAlgorithm = computed(() => selectedAlgorithm.value.endpoint === '/api/health/evaluate')
const isPredictionAlgorithm = computed(() => selectedAlgorithm.value.endpoint === '/api/health/predict')
const isProcessingAlgorithm = computed(() => selectedAlgorithm.value.endpoint === '/api/health/process')
const modelInfo = computed(() => modelStatus.value?.models?.[selectedAlgorithmKey.value] || null)
const modelReady = computed(() => Boolean(modelInfo.value?.trained))
const isGatAlgorithm = computed(() => selectedAlgorithmKey.value === 'gat_vae_reconstruction')
const gatDemo = ref(null)
const gatDemoError = ref('')
const gatDemoLoading = ref(false)
const gatDemoIndex = ref(0)
const gatDemoPlaying = ref(false)
let gatDemoPlaybackTimer = null
let gatDemoRequestId = 0
const modelStatusLabel = computed(() => modelReady.value ? '模型已加载' : '等待训练')
const gatDemoPoint = computed(() => gatDemo.value?.points?.[gatDemoIndex.value] || null)
const gatDemoPolyline = computed(() => {
  const points = gatDemo.value?.points || []
  if (points.length < 2) return ''
  return points.map((point, index) => {
    const x = (index / (points.length - 1)) * 640
    const y = 160 - (Math.max(0, Math.min(100, Number(point.overall_score || 0))) / 100) * 140 - 10
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
})
const gatDemoCursorX = computed(() => {
  const count = gatDemo.value?.points?.length || 1
  return count <= 1 ? 0 : (gatDemoIndex.value / (count - 1)) * 640
})
const gatDemoCursorY = computed(() => {
  const score = Number(gatDemoPoint.value?.overall_score || 0)
  return 160 - (Math.max(0, Math.min(100, score)) / 100) * 140 - 10
})
const runtimeDescription = computed(() => {
  if (selectedAlgorithm.value.key === 'gat_vae_reconstruction') return '当前完整协议帧 + 前12帧连续历史 → GAT拓扑编码 + GRU时序编码 → 演示测点下一帧重构误差 → 演示子系统健康度'
  if (isAssessmentAlgorithm.value) return `当前实时快照 → 演示维度参数特征 → ${selectedAlgorithm.value.description || '健康特征综合评估'} → 演示子系统健康度`
  if (isPredictionAlgorithm.value) return '当前实时快照填充演示窗口 → 三层网络 → 未来健康度与剩余寿命'
  if (isProcessingAlgorithm.value) return '当前实时快照 → 演示维度健康特征 → 多尺度分解 → 能量统计'
  return '当前实时快照 → 轻量规则计算 → 可解释结果'
})
const runtimeBadgeText = computed(() => {
  if (runtimeError.value && !evaluation.value && !prediction.value && !processing.value) return '异常'
  if (modelReady.value) return '在线'
  return '实时计算'
})
const runtimeBadgeClass = computed(() => {
  if (runtimeError.value && !evaluation.value && !prediction.value && !processing.value) return 'is-error'
  if (modelReady.value) return 'is-online'
  return 'is-placeholder'
})

const percent = (value) => `${Math.round(Number(value || 0) * 100)}%`
const scoreClass = (score) => {
  const value = Number(score)
  if (value >= 60) return 'score-good'
  if (value >= 30) return 'score-warn'
  return 'score-danger'
}

const stopGatDemoPlayback = () => {
  gatDemoPlaying.value = false
  if (gatDemoPlaybackTimer) window.clearInterval(gatDemoPlaybackTimer)
  gatDemoPlaybackTimer = null
}

const resetGatDemoPlayback = () => {
  stopGatDemoPlayback()
  gatDemoIndex.value = 0
}

const toggleGatDemoPlayback = () => {
  if (!gatDemo.value?.points?.length) return
  if (gatDemoPlaying.value) {
    stopGatDemoPlayback()
    return
  }
  gatDemoPlaying.value = true
  gatDemoPlaybackTimer = window.setInterval(() => {
    const lastIndex = gatDemo.value.points.length - 1
    gatDemoIndex.value = gatDemoIndex.value >= lastIndex ? 0 : gatDemoIndex.value + 1
  }, 250)
}

const seekGatDemo = (event) => {
  const nextIndex = Number(event.target.value)
  if (Number.isInteger(nextIndex)) gatDemoIndex.value = nextIndex
}

const loadGatDemo = async () => {
  const requestId = ++gatDemoRequestId
  gatDemoLoading.value = true
  gatDemoError.value = ''
  try {
    const response = await axios.get(`${API_PREFIX}/health/reconstruction/demo`, { params: { split: 'test', limit: 180 } })
    if (requestId !== gatDemoRequestId) return
    gatDemo.value = response.data?.data || null
    gatDemoIndex.value = 0
    if (!gatDemo.value?.points?.length) gatDemoError.value = '测试集回放中没有可展示的帧。'
  } catch (error) {
    if (requestId === gatDemoRequestId) gatDemoError.value = error.response?.data?.error || '测试集动态重构演示暂不可用。'
  } finally {
    if (requestId === gatDemoRequestId) gatDemoLoading.value = false
  }
}

const isStepAligned = (value, item) => {
  const step = Number(item.step)
  if (!Number.isFinite(step) || step <= 0) return true
  const min = Number(item.min)
  const quotient = (value - min) / step
  return Math.abs(quotient - Math.round(quotient)) <= 1e-9
}

const validateCurrentParams = () => {
  for (const item of currentParams.value) {
    const label = item.label || item.key
    if (item.value === null || item.value === undefined || String(item.value).trim() === '') {
      return `${label}不能为空`
    }
    const value = Number(item.value)
    if (!Number.isFinite(value)) {
      return `${label}必须是数字`
    }
    if (value < Number(item.min) || value > Number(item.max)) {
      return `${label}必须在 ${item.min} 到 ${item.max} 之间`
    }
    if (!isStepAligned(value, item)) {
      return Number(item.step) === 1
        ? `${label}必须是整数`
        : `${label}必须按 ${item.step} 的步长填写`
    }
  }
  return ''
}

const loadRuntime = async (algorithm = selectedAlgorithmKey.value, { background = false } = {}) => {
  if (background && (runtimeLoading.value || runtimeRefreshInFlight)) return
  const requestId = ++runtimeRequestId
  if (background) {
    runtimeRefreshInFlight = true
  } else {
    runtimeLoading.value = true
    runtimeError.value = ''
    runtimeWaitingMessage.value = ''
  }
  try {
    if (!background) {
      const modelResponse = await axios.get(`${API_PREFIX}/health/models`)
      if (requestId !== runtimeRequestId) return
      modelStatus.value = modelResponse.data?.data || modelStatus.value
      const configResponse = await axios.get(`${API_PREFIX}/algorithms/config`)
      if (requestId !== runtimeRequestId) return
      currentParams.value = (configResponse.data?.data?.[algorithm]?.params || []).map((item) => ({ ...item }))
    }
    const endpoint = allAlgorithms.value.find((item) => item.key === algorithm)?.endpoint
    if (endpoint === '/api/health/evaluate') {
      const response = await axios.get(`${API_PREFIX}/health/evaluate`, { params: { algorithm } })
      if (requestId === runtimeRequestId && response.data?.warming_up) {
        evaluation.value = null
        runtimeWaitingMessage.value = response.data.warming_up
      } else if (requestId === runtimeRequestId) {
        runtimeWaitingMessage.value = ''
        if (response.data?.data || !background) evaluation.value = response.data?.data || null
      }
    } else if (endpoint === '/api/health/predict') {
      const response = await axios.get(`${API_PREFIX}/health/predict`, { params: { algorithm } })
      if (requestId === runtimeRequestId && (response.data?.data || !background)) prediction.value = response.data?.data || null
    } else if (endpoint === '/api/health/process') {
      const response = await axios.get(`${API_PREFIX}/health/process`, { params: { algorithm } })
      if (requestId === runtimeRequestId && (response.data?.data || !background)) processing.value = response.data?.data || null
    }
    if (requestId === runtimeRequestId) {
      runtimeError.value = ''
      lastUpdatedText.value = new Date().toLocaleString('zh-CN')
    }
  } catch (error) {
    if (requestId === runtimeRequestId && !background) {
      const message = error.response?.data?.error || '模型服务暂时不可用，请先启动后端。'
      runtimeError.value = message
    }
  } finally {
    if (background) runtimeRefreshInFlight = false
    if (!background && requestId === runtimeRequestId) runtimeLoading.value = false
  }
}

const saveConfig = async () => {
  const validationError = validateCurrentParams()
  if (validationError) {
    ElMessage.error(validationError)
    return
  }
  configSaving.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/algorithms/config/${selectedAlgorithmKey.value}`, { params: currentParams.value })
    if (response.data?.params) {
      currentParams.value = currentParams.value.map((item) => ({
        ...item,
        value: response.data.params[item.key] ?? item.value
      }))
    }
    ElMessage.success(response.data?.requires_retrain ? '参数已保存，请点击“重训模型”后生效' : '超参数配置已保存')
  } catch (error) { ElMessage.error(error.response?.data?.error || '超参数保存失败') } finally { configSaving.value = false }
}

const saveCustomAlgorithm = async () => {
  customSaving.value = true
  try { await axios.post(`${API_PREFIX}/algorithms/custom`, customForm.value); ElMessage.success('自定义算法登记成功'); customDialogVisible.value = false; customForm.value = { name: '', category: '健康评估算法', file_path: '', config_path: '' } } catch (error) { ElMessage.error(error.response?.data?.error || '登记失败') } finally { customSaving.value = false }
}

const selectAlgorithm = async (item) => {
  stopGatDemoPlayback()
  selectedAlgorithmKey.value = item.key
  runtimeError.value = ''
  runtimeWaitingMessage.value = ''
  evaluation.value = null
  prediction.value = null
  processing.value = null
  if (item.endpoint === '/api/health/evaluate') {
    try {
      await axios.post(`${API_PREFIX}/health/algorithm`, { algorithm: item.key })
    } catch (error) {
      runtimeError.value = error.response?.data?.error || '算法切换失败'
    }
  }
  await loadRuntime(item.key)
  if (item.key === 'gat_vae_reconstruction') await loadGatDemo()
}

const handleRetrain = async () => {
  retrainLoading.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/health/retrain`)
    modelStatus.value = response.data?.data || null
    ElMessage.success('基础健康模型已完成重训，结果已刷新')
    await loadRuntime(selectedAlgorithmKey.value)
  } catch (error) {
    ElMessage.error('模型重训失败')
  } finally {
    retrainLoading.value = false
  }
}

const goBack = () => {
  router.push('/health')
}

onMounted(async () => {
  try {
    const catalogResponse = await axios.get(`${API_PREFIX}/algorithms/catalog`)
    const catalog = (catalogResponse.data?.data || []).filter((item) => item.implemented)
    const grouped = Object.entries(categoryTitles).map(([category, title]) => ({
      key: categoryKeys[category],
      title,
      algorithms: catalog.filter((item) => item.category === category).map((item) => ({ ...item, groupTitle: title }))
    })).filter((group) => group.algorithms.length)
    algorithmGroups.value = grouped
    if (!allAlgorithms.value.some((item) => item.key === selectedAlgorithmKey.value)) {
      selectedAlgorithmKey.value = allAlgorithms.value[0]?.key || ''
    }
    const response = await axios.get(`${API_PREFIX}/health/algorithm`)
    const active = response.data?.algorithm
    if (allAlgorithms.value.some((item) => item.key === active)) selectedAlgorithmKey.value = active
    await loadRuntime(selectedAlgorithmKey.value)
    if (selectedAlgorithmKey.value === 'gat_vae_reconstruction') await loadGatDemo()
  } catch (error) {
    runtimeError.value = error.response?.data?.error || '算法目录服务暂时不可用，请先启动后端。'
    await loadRuntime()
  }
  dashboardSocket = createDashboardSocket({
    onDashboardUpdate: () => {
      // Socket 高频推送时静默更新当前算法，保留上一条有效结果和在线徽标。
      if (refreshTimer) window.clearTimeout(refreshTimer)
      refreshTimer = window.setTimeout(() => {
        refreshTimer = null
        loadRuntime(selectedAlgorithmKey.value, { background: true })
      }, 220)
    }
  })
})

onUnmounted(() => {
  if (refreshTimer) window.clearTimeout(refreshTimer)
  refreshTimer = null
  stopGatDemoPlayback()
  gatDemoRequestId += 1
  dashboardSocket?.disconnect()
  dashboardSocket = null
})
</script>

<style scoped>
.algo-screen {
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

.panel {
  border: 1px solid rgba(87, 201, 255, 0.4);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 37, 92, 0.88), rgba(6, 24, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(34, 154, 255, 0.16);
}

.screen-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px;
}

.eyebrow {
  margin: 0;
  color: #86dfff;
  font-size: 11px;
  letter-spacing: 1.5px;
}

h1 {
  margin: 4px 0 0;
  font-size: 30px;
  color: #f2fbff;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.action-btn {
  border-radius: 8px;
}

.action-btn.ghost {
  background: #143768;
  color: #c6ecff;
  border-color: #3779b9;
}

.sim-toggle {
  height: 36px;
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
  grid-template-columns: 380px 1fr;
}

.sidebar,
.workspace {
  padding: 14px;
}

h2 {
  margin: 0;
  color: #99e6ff;
  font-size: 18px;
}

.group-block {
  margin-top: 12px;
}

h3 {
  margin: 0 0 8px;
  color: #8fdaf6;
  font-size: 14px;
  font-weight: 600;
}

.algo-list {
  display: grid;
  gap: 8px;
}

.algo-card {
  text-align: left;
  border: 1px solid rgba(99, 205, 255, 0.3);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(13, 51, 111, 0.85), rgba(11, 35, 85, 0.85));
  color: #d7f4ff;
  padding: 10px 12px;
  cursor: pointer;
  transition: 0.2s ease;
}

.algo-card strong {
  display: block;
  font-size: 14px;
}

.implemented-tag {
  display: inline-block;
  margin-left: 6px;
  padding: 2px 5px;
  border: 1px solid rgba(86, 255, 192, 0.45);
  border-radius: 4px;
  color: #56ffc0;
  font-size: 10px;
  font-style: normal;
  font-weight: 500;
  vertical-align: 2px;
}

.algo-card span {
  display: block;
  margin-top: 4px;
  color: #8fd7ef;
  font-size: 12px;
  line-height: 1.45;
}

.algo-card:hover {
  border-color: rgba(125, 226, 255, 0.6);
}

.algo-card.active {
  border-color: #7be7ff;
  box-shadow: 0 0 12px rgba(95, 223, 255, 0.25);
}

.workspace-head {
  border-bottom: 1px solid rgba(95, 197, 255, 0.26);
  padding-bottom: 10px;
}

.group-name {
  margin: 0;
  color: #8ed4f4;
  font-size: 12px;
}

.status-box {
  border: 1px solid rgba(96, 205, 255, 0.24);
  border-radius: 8px;
  background: rgba(8, 26, 64, 0.58);
  padding: 12px;
}

h4 {
  margin: 0;
  color: #9fe8ff;
  font-size: 14px;
}

.runtime-box,
.status-box {
  margin-top: 12px;
}

.runtime-box {
  border: 1px solid rgba(96, 205, 255, 0.34);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(8, 34, 82, 0.72), rgba(7, 24, 61, 0.72));
  padding: 12px;
}

.gat-demo-box {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(86, 255, 192, 0.3);
  border-radius: 8px;
  background: linear-gradient(180deg, rgba(8, 45, 79, 0.72), rgba(7, 24, 61, 0.78));
}

.gat-demo-head,
.gat-demo-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.gat-demo-head h3 {
  margin: 4px 0 0;
  color: #c9f4ff;
  font-size: 16px;
}

.gat-demo-caption,
.gat-demo-chart-caption {
  color: #9edff4;
  font-size: 11px;
  line-height: 1.5;
}

.gat-demo-caption { margin: 8px 0 12px; }
.gat-demo-metrics { margin-bottom: 10px; }
.gat-demo-metrics .metric-card strong { font-size: 17px; }

.gat-demo-chart {
  margin: 10px 0 7px;
  padding: 8px;
  border: 1px solid rgba(107, 215, 255, 0.2);
  border-radius: 7px;
  background: rgba(4, 20, 53, 0.62);
}

.gat-demo-chart svg { display: block; width: 100%; height: 150px; }
.gat-demo-line { fill: none; stroke: #56ffc0; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
.gat-demo-threshold { stroke: rgba(255, 226, 122, 0.62); stroke-width: 1; stroke-dasharray: 5 5; }
.gat-demo-cursor { stroke: rgba(119, 222, 255, 0.8); stroke-width: 1.5; stroke-dasharray: 3 3; }
.gat-demo-marker { fill: #fff1a6; stroke: #06234f; stroke-width: 2; }
.gat-demo-chart-caption { display: flex; justify-content: space-between; gap: 8px; font-size: 10px; }

.gat-demo-readout {
  padding: 8px 10px;
  border-radius: 6px;
  color: #b9eafb;
  background: rgba(4, 20, 53, 0.46);
  font-size: 11px;
  line-height: 1.55;
}

.gat-demo-range { display: block; width: 100%; margin: 8px 0 12px; accent-color: #56ffc0; }
.gat-demo-score-list { gap: 6px; }

.runtime-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.runtime-head p {
  margin: 5px 0 0;
  color: #9edff4;
  font-size: 12px;
  line-height: 1.45;
}

.runtime-badge {
  flex: 0 0 auto;
  padding: 4px 8px;
  border: 1px solid rgba(125, 226, 255, 0.35);
  border-radius: 999px;
  color: #c8f4ff;
  font-size: 11px;
}

.runtime-badge.is-online {
  border-color: rgba(86, 255, 192, 0.5);
  color: #56ffc0;
}

.runtime-badge.is-loading {
  color: #ffe27a;
}

.runtime-badge.is-error,
.error-text {
  color: #ff9eb3;
}

.runtime-empty {
  padding: 20px 8px 8px;
  color: #9edff4;
  font-size: 13px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.metric-card {
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(107, 215, 255, 0.2);
  border-radius: 7px;
  background: rgba(4, 20, 53, 0.62);
}

.metric-card span,
.metric-card small {
  display: block;
  color: #8bcfe8;
  font-size: 11px;
}

.metric-card strong {
  display: block;
  margin: 4px 0 2px;
  color: #effbff;
  font-size: 23px;
  line-height: 1.1;
}

.metric-card.primary-metric strong {
  color: #56ffc0;
}

.subsystem-score-list {
  display: grid;
  gap: 7px;
  margin-top: 12px;
}

.subsystem-score-row {
  display: grid;
  grid-template-columns: 138px minmax(80px, 1fr) 40px;
  align-items: center;
  gap: 8px;
  color: #c8effb;
  font-size: 12px;
}

.score-track {
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(123, 190, 225, 0.15);
}

.score-track i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2a9bff, #56ffc0);
}

.subsystem-score-row strong,
.forecast-card strong {
  text-align: right;
}

.score-good {
  color: #56ffc0 !important;
}

.score-warn {
  color: #ffe27a !important;
}

.score-danger {
  color: #ff718c !important;
}

.forecast-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  margin-top: 12px;
}

.forecast-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(107, 215, 255, 0.2);
  border-radius: 7px;
  background: rgba(4, 20, 53, 0.62);
}

.forecast-card span,
.forecast-card small {
  display: block;
}

.forecast-card span {
  color: #c8effb;
  font-size: 12px;
}

.forecast-card small {
  margin-top: 3px;
  color: #8bcfe8;
  font-size: 11px;
}

.status-box {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.status-item {
  border: 1px solid rgba(117, 216, 255, 0.24);
  border-radius: 8px;
  background: rgba(7, 23, 57, 0.5);
  padding: 10px;
}

.status-item span {
  display: block;
  color: #8bcfe8;
  font-size: 12px;
}

.status-item strong {
  display: block;
  margin-top: 6px;
  color: #effbff;
  font-size: 14px;
}

.status-item strong.online {
  color: #56ffc0;
}

.status-item strong.offline {
  color: #ffe27a;
}

.hyperparam-box {
  margin-top: 12px;
  padding: 12px;
  border: 1px solid rgba(96, 205, 255, 0.34);
  border-radius: 8px;
  background: rgba(8, 26, 64, 0.58);
}

.hyperparam-list {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.hyperparam-list label {
  display: grid;
  grid-template-columns: minmax(150px, 1fr) 132px 80px 58px;
  align-items: center;
  gap: 10px;
  padding: 9px 10px;
  border: 1px solid rgba(107, 215, 255, 0.2);
  border-radius: 7px;
  background: rgba(4, 20, 53, 0.62);
  color: #c8effb;
  font-size: 12px;
}

.hyperparam-list input {
  width: 100%;
  box-sizing: border-box;
  padding: 6px 8px;
  border: 1px solid rgba(125, 226, 255, 0.42);
  border-radius: 5px;
  background: #071b45;
  color: #effbff;
}

.hyperparam-list small {
  color: #82cce6;
  text-align: right;
}

.hyperparam-list em {
  color: #56ffc0;
  font-size: 11px;
  font-style: normal;
  text-align: right;
}

@media (max-width: 1024px) {
  .screen-grid {
    grid-template-columns: 1fr;
  }

  .status-box {
    grid-template-columns: 1fr;
  }

  .metric-grid,
  .forecast-list {
    grid-template-columns: 1fr;
  }

  .screen-header {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 680px) {
  .subsystem-score-row {
    grid-template-columns: 112px minmax(60px, 1fr) 36px;
    font-size: 11px;
  }

  .hyperparam-list label {
    grid-template-columns: 1fr 100px;
  }

  .hyperparam-list small,
  .hyperparam-list em {
    text-align: left;
  }

  .gat-demo-head,
  .gat-demo-controls {
    align-items: flex-start;
  }

  .gat-demo-chart-caption { font-size: 9px; }
}
</style>
