<template>
  <section class="bearing-diagnosis-screen">
    <header class="bearing-title-strip">
      <div class="bearing-heading">
        <span class="bearing-eyebrow">COMPONENT DIAGNOSTICS / PROTOTYPE 01</span>
        <h1>轴承部件故障诊断</h1>
        <p>天线方位传动链 · 面向部件的健康度与故障原因判别</p>
      </div>
      <div class="bearing-toolbar">
        <span class="bearing-replay-chip"><i></i>前端仿真数据</span>
        <button type="button" class="bearing-tool-btn" @click="resetInputs">恢复基线</button>
        <button type="button" class="bearing-run-btn" @click="runDiagnosis">重新诊断 <b>↵</b></button>
      </div>
    </header>

    <div class="bearing-summary-grid">
      <article class="bearing-summary-card bearing-summary-health">
        <span class="summary-label">当前健康度</span>
        <strong>{{ diagnosis.score }}<small>/100</small></strong>
        <span class="summary-state" :class="diagnosis.statusClass">{{ diagnosis.status }}</span>
      </article>
      <article class="bearing-summary-card">
        <span class="summary-label">主判别结果</span>
        <strong class="summary-result">{{ diagnosis.primaryCause }}</strong>
        <span class="summary-note">证据融合 · {{ diagnosis.confidence }}% 置信度</span>
      </article>
      <article class="bearing-summary-card">
        <span class="summary-label">诊断对象</span>
        <strong class="summary-result">{{ selectedBearingLabel }}</strong>
        <span class="summary-note">方位传动链 / 轴承测点组</span>
      </article>
      <article class="bearing-summary-card">
        <span class="summary-label">本次诊断</span>
        <strong class="summary-result">{{ runNumber.toString().padStart(2, '0') }} <em>RUN</em></strong>
        <span class="summary-note">最近更新 {{ lastUpdated }}</span>
      </article>
    </div>

    <div class="bearing-workbench">
      <aside class="bearing-panel bearing-input-panel">
        <div class="bearing-panel-heading">
          <div><span class="panel-kicker">01 / INPUT</span><h2>诊断输入</h2></div>
          <span class="panel-state">LOCAL</span>
        </div>

        <label class="bearing-field">
          <span>诊断部件</span>
          <select v-model="selectedBearing">
            <option v-for="item in bearingOptions" :key="item.id" :value="item.id">{{ item.label }}</option>
          </select>
        </label>

        <div class="bearing-field">
          <span>快速场景</span>
          <div class="bearing-mode-grid">
            <button
              v-for="mode in modeOptions"
              :key="mode.key"
              type="button"
              :class="{ active: activeMode === mode.key }"
              @click="selectMode(mode.key)"
            >{{ mode.label }}</button>
          </div>
        </div>

        <div class="bearing-input-divider"><span>关键测点 / LIVE VALUES</span></div>

        <label v-for="field in inputFields" :key="field.key" class="bearing-range-field">
          <span class="range-topline"><b>{{ field.label }}</b><strong>{{ formatInput(field) }}<small>{{ field.unit }}</small></strong></span>
          <input v-model.number="inputs[field.key]" type="range" :min="field.min" :max="field.max" :step="field.step" @input="activeMode = 'custom'" />
          <span class="range-scale"><i>{{ field.min }}{{ field.unit }}</i><i>{{ field.max }}{{ field.unit }}</i></span>
        </label>

        <div class="bearing-threshold-note">
          <span class="note-dot"></span>
          <p><b>判定规则</b> 健康度 ≥ 60 为正常，30–59 为故障，低于 30 为报废。</p>
        </div>
      </aside>

      <main class="bearing-main-column">
        <article class="bearing-panel bearing-result-panel">
          <div class="bearing-panel-heading result-heading">
            <div><span class="panel-kicker">02 / ASSESSMENT</span><h2>轴承健康状态</h2></div>
            <span class="diagnosis-timestamp">{{ lastUpdated }} · {{ diagnosis.status }}</span>
          </div>
          <div class="bearing-result-layout">
            <div class="bearing-gauge-wrap">
              <svg class="bearing-gauge" viewBox="0 0 180 180" role="img" aria-label="轴承健康度">
                <circle class="gauge-track" cx="90" cy="90" r="70" />
                <circle class="gauge-value" :class="diagnosis.statusClass" cx="90" cy="90" r="70" :style="{ strokeDashoffset: gaugeOffset }" />
              </svg>
              <div class="gauge-center"><strong>{{ diagnosis.score }}</strong><span>HEALTH</span></div>
              <span class="gauge-caption">综合健康度</span>
            </div>
            <div class="bearing-cause-column">
              <div class="cause-column-heading"><span>故障原因候选</span><small>按当前证据排序</small></div>
              <div v-for="cause in diagnosis.causes" :key="cause.key" class="cause-row">
                <div class="cause-row-title"><span>{{ cause.name }}</span><strong>{{ cause.probability }}%</strong></div>
                <div class="cause-track"><i :class="cause.tone" :style="{ width: `${cause.probability}%` }"></i></div>
                <small>{{ cause.evidence }}</small>
              </div>
            </div>
          </div>
        </article>

        <article class="bearing-panel bearing-signal-panel">
          <div class="bearing-panel-heading">
            <div><span class="panel-kicker">03 / SIGNALS</span><h2>关键测点波形</h2></div>
            <span class="signal-window">最近 60 s · 采样窗口</span>
          </div>
          <div class="signal-grid">
            <div v-for="signal in signals" :key="signal.key" class="signal-card">
              <div class="signal-card-top"><span>{{ signal.label }}</span><strong>{{ signal.value }}<small>{{ signal.unit }}</small></strong></div>
              <svg viewBox="0 0 320 88" preserveAspectRatio="none" aria-hidden="true">
                <path class="signal-grid-line" d="M0 22H320 M0 44H320 M0 66H320" />
                <polyline :class="signal.tone" :points="signal.points" />
              </svg>
              <span class="signal-foot"><i :class="signal.tone"></i>{{ signal.note }}</span>
            </div>
          </div>
        </article>
      </main>

      <aside class="bearing-side-column">
        <article class="bearing-panel evidence-panel">
          <div class="bearing-panel-heading">
            <div><span class="panel-kicker">04 / EVIDENCE</span><h2>故障证据链</h2></div>
            <span class="evidence-count">{{ evidenceItems.length }} 条</span>
          </div>
          <div class="evidence-list">
            <div v-for="item in evidenceItems" :key="item.label" class="evidence-item">
              <span class="evidence-icon" :class="item.tone">{{ item.icon }}</span>
              <div><strong>{{ item.label }}</strong><p>{{ item.detail }}</p></div>
              <span class="evidence-state" :class="item.tone">{{ item.state }}</span>
            </div>
          </div>
        </article>

        <article class="bearing-panel action-panel">
          <div class="bearing-panel-heading">
            <div><span class="panel-kicker">05 / ACTION</span><h2>处置建议</h2></div>
          </div>
          <div class="action-banner" :class="diagnosis.statusClass">
            <span>{{ diagnosis.actionLevel }}</span>
            <strong>{{ diagnosis.actionTitle }}</strong>
          </div>
          <ol class="action-list">
            <li v-for="(action, index) in diagnosis.actions" :key="action"><b>0{{ index + 1 }}</b><span>{{ action }}</span></li>
          </ol>
        </article>

        <article class="bearing-panel parameter-panel">
          <div class="bearing-panel-heading"><div><span class="panel-kicker">06 / TELEMETRY</span><h2>测点快照</h2></div></div>
          <div class="parameter-table">
            <div v-for="field in inputFields" :key="field.key" class="parameter-row"><span>{{ field.shortLabel }}</span><strong>{{ formatInput(field) }}</strong><em>{{ field.unit }}</em></div>
          </div>
        </article>
      </aside>
    </div>

    <footer class="bearing-method-note">
      <span><i></i> 前端演示模式</span>
      <span>当前算法：规则加权基线 · 后续可替换为部件级时序模型</span>
      <span>目标：先验证部件诊断界面与交互闭环</span>
    </footer>
  </section>
</template>

<script setup>
import { computed, ref } from 'vue'

const bearingOptions = [
  { id: 'azimuth-drive-a', label: '方位传动轴承 A · AZ-BRG-01' },
  { id: 'azimuth-drive-b', label: '方位传动轴承 B · AZ-BRG-02' },
  { id: 'elevation-drive-a', label: '俯仰传动轴承 A · EL-BRG-01' }
]

const modeOptions = [
  { key: 'normal', label: '健康基线' },
  { key: 'outer-race', label: '外圈点蚀' },
  { key: 'inner-race', label: '内圈损伤' },
  { key: 'lubrication', label: '润滑异常' },
  { key: 'misalignment', label: '不对中' }
]

const profiles = {
  normal: { vibration: 1.2, temperature: 39, noise: 0.08, axial: 0.08 },
  'outer-race': { vibration: 4.8, temperature: 66, noise: 0.33, axial: 0.24 },
  'inner-race': { vibration: 4.6, temperature: 64, noise: 0.3, axial: 0.22 },
  lubrication: { vibration: 3.6, temperature: 65, noise: 0.5, axial: 0.16 },
  misalignment: { vibration: 4, temperature: 58, noise: 0.25, axial: 0.5 }
}

const selectedBearing = ref('azimuth-drive-a')
const activeMode = ref('outer-race')
const inputs = ref({ ...profiles['outer-race'] })
const runNumber = ref(1)
const lastUpdated = ref('14:32:08')

const inputFields = [
  { key: 'vibration', label: '振动 RMS', shortLabel: '振动 RMS', min: 0.2, max: 6, step: 0.1, unit: ' mm/s' },
  { key: 'temperature', label: '轴承温度', shortLabel: '轴承温度', min: 20, max: 90, step: 1, unit: ' °C' },
  { key: 'noise', label: '高频噪声', shortLabel: '高频噪声', min: 0.02, max: 0.6, step: 0.01, unit: ' g' },
  { key: 'axial', label: '轴向位移', shortLabel: '轴向位移', min: 0.02, max: 0.5, step: 0.01, unit: ' mm' }
]

const selectedBearingLabel = computed(() => bearingOptions.find((item) => item.id === selectedBearing.value)?.label.split(' · ')[0] || '--')

const clamp = (value, min, max) => Math.min(max, Math.max(min, value))

const scoreValue = computed(() => {
  const value = inputs.value
  const penalty = Math.max(0, value.vibration - 1.2) * 7.8
    + Math.max(0, value.temperature - 40) * 0.37
    + Math.max(0, value.noise - 0.08) * 31
    + Math.max(0, value.axial - 0.08) * 22
  return Math.round(clamp(100 - penalty, 0, 100))
})

const statusMeta = computed(() => {
  if (scoreValue.value >= 60) return { label: '正常', cls: 'ok' }
  if (scoreValue.value >= 30) return { label: '故障', cls: 'warning' }
  return { label: '报废', cls: 'danger' }
})

const modeCauseWeights = {
  normal: { outer: 8, lubrication: 5, inner: 6, alignment: 7 },
  'outer-race': { outer: 93, lubrication: 34, inner: 41, alignment: 19 },
  'inner-race': { outer: 37, lubrication: 26, inner: 91, alignment: 22 },
  lubrication: { outer: 27, lubrication: 89, inner: 28, alignment: 24 },
  misalignment: { outer: 22, lubrication: 31, inner: 24, alignment: 88 },
  custom: { outer: 30, lubrication: 24, inner: 28, alignment: 26 }
}

const causeDefinitions = [
  { key: 'outer', name: '外圈点蚀 / 滚道损伤', tone: 'danger', evidence: '振动 RMS 与高频噪声同步升高' },
  { key: 'inner', name: '内圈或滚动体局部损伤', tone: 'warning', evidence: '冲击成分与轴向位移存在耦合' },
  { key: 'lubrication', name: '润滑不足或污染', tone: 'amber', evidence: '温升和高频能量持续偏高' },
  { key: 'alignment', name: '轴系不对中 / 安装偏差', tone: 'blue', evidence: '轴向位移超出基线区间' }
]

const diagnosis = computed(() => {
  const weights = modeCauseWeights[activeMode.value] || modeCauseWeights.custom
  const signalBoost = {
    outer: Math.max(0, inputs.value.vibration - 2.4) * 4 + Math.max(0, inputs.value.noise - 0.2) * 20,
    inner: Math.max(0, inputs.value.vibration - 2.8) * 3 + Math.max(0, inputs.value.axial - 0.16) * 18,
    lubrication: Math.max(0, inputs.value.temperature - 48) * 0.55 + Math.max(0, inputs.value.noise - 0.18) * 19,
    alignment: Math.max(0, inputs.value.axial - 0.16) * 35
  }
  const causes = causeDefinitions
    .map((item) => ({ ...item, probability: Math.round(clamp(weights[item.key] + signalBoost[item.key], 2, 98)) }))
    .sort((a, b) => b.probability - a.probability)
  const top = causes[0]
  const isNormal = scoreValue.value >= 60 && top.probability < 45
  const primaryCause = isNormal ? '未发现明确故障' : top.name
  const confidence = isNormal
    ? 92
    : Math.round(clamp(78 + Math.abs(top.probability - causes[1].probability) * 0.35, 78, 98))
  const actionTitle = scoreValue.value >= 60 ? '继续观察' : scoreValue.value >= 30 ? '建议安排复核' : '建议立即停机检查'
  const actionLevel = scoreValue.value >= 60 ? 'LEVEL 0 / NORMAL' : scoreValue.value >= 30 ? 'LEVEL 1 / WARNING' : 'LEVEL 2 / CRITICAL'
  const actions = scoreValue.value >= 60
    ? ['保持当前润滑周期，继续采集振动趋势', '在下一次巡检中复核轴承间隙', '累计 3 个窗口异常后升级诊断']
    : top.key === 'lubrication'
      ? ['检查润滑脂状态与补脂通道', '复核温度和高频噪声的连续趋势', '完成维护后重新执行部件诊断']
      : ['降低传动负载并安排现场复核', '检查轴承座、滚道和安装同心度', '保留当前窗口数据用于后续模型训练']
  return {
    score: scoreValue.value,
    status: statusMeta.value.label,
    statusClass: statusMeta.value.cls,
    primaryCause,
    confidence,
    causes,
    actionTitle,
    actionLevel,
    actions
  }
})

const gaugeOffset = computed(() => 440 - (440 * diagnosis.value.score) / 100)

const formatInput = (field) => {
  const value = Number(inputs.value[field.key])
  return field.step < 0.1 ? value.toFixed(2) : field.step < 1 ? value.toFixed(1) : value.toFixed(0)
}

const signals = computed(() => {
  const value = inputs.value
  const createPoints = (base, amplitude, frequency) => Array.from({ length: 42 }, (_, index) => {
    const x = (index / 41) * 320
    const jitter = Math.sin(index * frequency) * amplitude + Math.sin(index * 0.49) * amplitude * 0.35
    const y = clamp(base + jitter + (index > 27 ? (index - 27) * amplitude * 0.09 : 0), 7, 81)
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
  return [
    { key: 'vibration', label: '振动包络', value: formatInput(inputFields[0]), unit: 'mm/s', points: createPoints(44, 8 + value.vibration * 1.8, 0.85), tone: diagnosis.value.score < 60 ? 'danger' : 'ok', note: value.vibration > 3 ? '冲击峰值偏高' : '处于基线区间' },
    { key: 'temperature', label: '温度趋势', value: formatInput(inputFields[1]), unit: '°C', points: createPoints(51 - (value.temperature - 40) * 0.18, 3 + Math.max(0, value.temperature - 50) * 0.13, 0.32), tone: value.temperature > 55 ? 'warning' : 'ok', note: value.temperature > 55 ? '温升需持续观察' : '无明显温升' },
    { key: 'noise', label: '高频噪声', value: formatInput(inputFields[2]), unit: 'g', points: createPoints(42, 5 + value.noise * 26, 1.7), tone: value.noise > 0.24 ? 'danger' : 'blue', note: value.noise > 0.24 ? '高频能量异常' : '频带能量稳定' }
  ]
})

const evidenceItems = computed(() => [
  { icon: 'V', label: '振动 RMS', detail: `${formatInput(inputFields[0])} mm/s · 基线 1.2`, state: inputs.value.vibration > 2.4 ? '异常' : '正常', tone: inputs.value.vibration > 2.4 ? 'danger' : 'ok' },
  { icon: 'T', label: '轴承温度', detail: `${formatInput(inputFields[1])} °C · 基线 39`, state: inputs.value.temperature > 55 ? '偏高' : '正常', tone: inputs.value.temperature > 55 ? 'warning' : 'ok' },
  { icon: 'N', label: '高频噪声', detail: `${formatInput(inputFields[2])} g · 频带 1–5 kHz`, state: inputs.value.noise > 0.24 ? '异常' : '正常', tone: inputs.value.noise > 0.24 ? 'danger' : 'ok' },
  { icon: 'A', label: '轴向位移', detail: `${formatInput(inputFields[3])} mm · 基线 0.08`, state: inputs.value.axial > 0.22 ? '偏高' : '正常', tone: inputs.value.axial > 0.22 ? 'warning' : 'ok' }
])

function selectMode(key) {
  activeMode.value = key
  inputs.value = { ...profiles[key] }
}

function resetInputs() {
  activeMode.value = 'normal'
  inputs.value = { ...profiles.normal }
}

function runDiagnosis() {
  runNumber.value += 1
  const now = new Date()
  lastUpdated.value = now.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.bearing-diagnosis-screen {
  --bearing-bg: #031126;
  --bearing-panel: rgba(5, 26, 58, .92);
  --bearing-panel-deep: rgba(3, 19, 45, .94);
  --bearing-line: rgba(50, 172, 236, .45);
  --bearing-line-soft: rgba(56, 154, 216, .19);
  --bearing-text: #e0f5ff;
  --bearing-muted: #7ea9c8;
  --bearing-cyan: #55d9ff;
  --bearing-green: #48e6a2;
  --bearing-yellow: #ffd35e;
  --bearing-red: #ff6678;
  position: relative;
  min-height: calc(100vh - 79px);
  overflow: hidden;
  padding: 12px;
  color: var(--bearing-text);
  background:
    linear-gradient(rgba(61, 157, 220, .035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(61, 157, 220, .035) 1px, transparent 1px),
    radial-gradient(circle at 60% -15%, rgba(17, 108, 197, .3), transparent 42%),
    linear-gradient(180deg, #041638 0%, var(--bearing-bg) 68%);
  background-size: 32px 32px, 32px 32px, auto, auto;
  border: 1px solid rgba(54, 169, 236, .5);
  box-shadow: inset 0 0 40px rgba(0, 112, 203, .16);
}

.bearing-title-strip,
.bearing-summary-card,
.bearing-panel,
.bearing-method-note { border: 1px solid var(--bearing-line); background: linear-gradient(160deg, rgba(8, 42, 85, .96), var(--bearing-panel-deep)); box-shadow: inset 0 0 12px rgba(28, 144, 224, .09); }
.bearing-title-strip { display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 64px; padding: 8px 14px; }
.bearing-heading { min-width: 0; }
.bearing-eyebrow, .panel-kicker { display: block; color: #61ccef; font: 9px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace; letter-spacing: 1.5px; }
.bearing-heading h1 { margin: 3px 0 1px; color: #f3fcff; font-size: clamp(18px, 2vw, 27px); letter-spacing: 2px; text-shadow: 0 0 12px rgba(55, 205, 255, .38); }
.bearing-heading p { margin: 0; color: var(--bearing-muted); font-size: 11px; }
.bearing-toolbar { display: flex; align-items: center; gap: 8px; flex: 0 0 auto; }
.bearing-replay-chip { display: inline-flex; align-items: center; gap: 6px; color: #8decc4; font-size: 10px; white-space: nowrap; }
.bearing-replay-chip i, .bearing-method-note i { width: 6px; height: 6px; display: inline-block; border-radius: 50%; background: var(--bearing-green); box-shadow: 0 0 8px rgba(72, 230, 162, .7); }
.bearing-tool-btn, .bearing-run-btn { min-height: 29px; padding: 0 10px; border: 1px solid rgba(75, 190, 243, .45); color: #b4eaff; background: rgba(11, 64, 116, .72); cursor: pointer; font-size: 10px; }
.bearing-tool-btn:hover, .bearing-run-btn:hover { border-color: var(--bearing-cyan); color: white; }
.bearing-run-btn { color: #062143; border-color: #52d6ff; background: linear-gradient(180deg, #74e2ff, #31aeda); font-weight: 700; }
.bearing-run-btn b { margin-left: 5px; font-size: 12px; }

.bearing-summary-grid { display: grid; grid-template-columns: 1.1fr 1.55fr 1.3fr 1.15fr; gap: 8px; margin-top: 8px; }
.bearing-summary-card { min-height: 74px; display: grid; align-content: center; gap: 4px; padding: 9px 12px; }
.summary-label { color: #77a9c7; font-size: 10px; }
.bearing-summary-card > strong { color: #f4fcff; font-size: 24px; line-height: 1; }
.bearing-summary-card > strong small { margin-left: 2px; color: #87b5cd; font-size: 11px; font-weight: 400; }
.summary-state { width: fit-content; padding: 2px 7px; border: 1px solid currentColor; font-size: 9px; }
.summary-state.ok { color: var(--bearing-green); }
.summary-state.warning { color: var(--bearing-yellow); }
.summary-state.danger { color: var(--bearing-red); }
.summary-result { font-size: 16px !important; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.summary-result em { margin-left: 5px; color: var(--bearing-cyan); font: 9px ui-monospace, monospace; font-style: normal; }
.summary-note { color: #769fba; font-size: 9px; }

.bearing-workbench { display: grid; grid-template-columns: 218px minmax(0, 1fr) 270px; gap: 8px; margin-top: 8px; }
.bearing-panel { min-width: 0; overflow: hidden; }
.bearing-input-panel, .evidence-panel, .action-panel, .parameter-panel { padding: 11px; }
.bearing-panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; margin-bottom: 10px; }
.bearing-panel-heading h2 { margin: 4px 0 0; color: #eaf9ff; font-size: 15px; font-weight: 600; letter-spacing: .5px; }
.panel-state, .evidence-count, .signal-window, .diagnosis-timestamp { color: #6f9ab7; font: 9px ui-monospace, monospace; }
.bearing-field { display: grid; gap: 5px; margin: 11px 0; color: #92bdd6; font-size: 10px; }
.bearing-field select { width: 100%; height: 31px; padding: 0 7px; border: 1px solid rgba(64, 177, 230, .42); color: #d4f5ff; background: #062454; font-size: 10px; outline: none; }
.bearing-mode-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 5px; }
.bearing-mode-grid button { min-height: 27px; padding: 0 3px; border: 1px solid rgba(64, 153, 207, .28); color: #86b0c8; background: rgba(5, 39, 79, .72); cursor: pointer; font-size: 9px; }
.bearing-mode-grid button:hover, .bearing-mode-grid button.active { border-color: var(--bearing-cyan); color: #effcff; background: rgba(18, 120, 169, .65); box-shadow: inset 0 0 8px rgba(54, 218, 255, .13); }
.bearing-input-divider { margin: 16px 0 10px; border-top: 1px solid var(--bearing-line-soft); color: #56b8dd; font: 8px ui-monospace, monospace; letter-spacing: .6px; }
.bearing-input-divider span { position: relative; top: -7px; padding-right: 6px; background: #061e48; }
.bearing-range-field { display: grid; gap: 5px; margin: 13px 0; }
.range-topline, .range-scale { display: flex; justify-content: space-between; gap: 5px; }
.range-topline { color: #9fc9de; font-size: 10px; }
.range-topline strong { color: #f0fcff; font: 11px ui-monospace, monospace; }
.range-topline strong small { color: #75a4bf; font-size: 8px; }
.range-scale { color: #5c88a4; font-size: 8px; }
.bearing-range-field input { width: 100%; accent-color: var(--bearing-cyan); cursor: pointer; }
.bearing-threshold-note { display: flex; gap: 8px; margin-top: 18px; padding: 8px; border: 1px solid rgba(255, 211, 94, .25); color: #c5b87c; background: rgba(91, 74, 25, .18); font-size: 9px; line-height: 1.5; }
.bearing-threshold-note p { margin: 0; }
.note-dot { flex: 0 0 6px; width: 6px; height: 6px; margin-top: 4px; border-radius: 50%; background: var(--bearing-yellow); }

.bearing-main-column, .bearing-side-column { display: grid; min-width: 0; gap: 8px; }
.bearing-main-column { grid-template-rows: minmax(330px, auto) minmax(230px, 1fr); }
.bearing-side-column { grid-template-rows: auto auto 1fr; }
.bearing-result-panel, .bearing-signal-panel { padding: 11px 12px; }
.result-heading { align-items: center; }
.bearing-result-layout { display: grid; grid-template-columns: 178px minmax(0, 1fr); align-items: center; gap: 18px; min-height: 275px; }
.bearing-gauge-wrap { position: relative; display: grid; place-items: center; min-height: 220px; }
.bearing-gauge { width: 178px; height: 178px; transform: rotate(-90deg); }
.gauge-track, .gauge-value { fill: none; stroke-width: 9; }
.gauge-track { stroke: rgba(58, 133, 180, .18); }
.gauge-value { stroke: var(--bearing-cyan); stroke-linecap: square; stroke-dasharray: 440; transition: stroke-dashoffset .35s ease; filter: drop-shadow(0 0 7px rgba(82, 214, 255, .45)); }
.gauge-value.ok { stroke: var(--bearing-green); }
.gauge-value.warning { stroke: var(--bearing-yellow); }
.gauge-value.danger { stroke: var(--bearing-red); }
.gauge-center { position: absolute; display: grid; justify-items: center; gap: 1px; }
.gauge-center strong { color: #f2fcff; font-size: 44px; line-height: 1; text-shadow: 0 0 12px rgba(77, 214, 255, .4); }
.gauge-center span { color: #73b3d0; font: 9px ui-monospace, monospace; letter-spacing: 2px; }
.gauge-caption { position: absolute; bottom: 2px; color: #7daac3; font-size: 10px; }
.cause-column-heading { display: flex; justify-content: space-between; margin-bottom: 8px; color: #a6d2e5; font-size: 11px; }
.cause-column-heading small { color: #638da8; font-size: 9px; }
.cause-row { padding: 9px 0; border-bottom: 1px solid rgba(68, 145, 197, .13); }
.cause-row:last-child { border-bottom: 0; }
.cause-row-title { display: flex; justify-content: space-between; gap: 8px; color: #ccecf7; font-size: 10px; }
.cause-row-title strong { color: #effcff; font: 11px ui-monospace, monospace; }
.cause-track { height: 5px; margin: 6px 0 4px; background: rgba(53, 115, 157, .2); }
.cause-track i { display: block; height: 100%; background: var(--bearing-cyan); transition: width .3s ease; }
.cause-track i.danger { background: var(--bearing-red); }
.cause-track i.warning { background: var(--bearing-yellow); }
.cause-track i.amber { background: #ffad5c; }
.cause-track i.blue { background: #7b9dff; }
.cause-row > small { color: #6e9ab2; font-size: 9px; }

.signal-window { padding-top: 4px; }
.signal-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; }
.signal-card { min-width: 0; padding: 7px; border: 1px solid rgba(67, 160, 215, .2); background: rgba(3, 22, 51, .7); }
.signal-card-top { display: flex; align-items: center; justify-content: space-between; gap: 6px; color: #94bdd3; font-size: 10px; }
.signal-card-top strong { color: #edfaff; font: 12px ui-monospace, monospace; }
.signal-card-top strong small { color: #6997b2; font-size: 8px; }
.signal-card svg { display: block; width: 100%; height: 88px; margin-top: 7px; border-top: 1px solid rgba(77, 157, 207, .12); border-bottom: 1px solid rgba(77, 157, 207, .12); background: linear-gradient(rgba(68, 144, 195, .05) 1px, transparent 1px); background-size: 100% 22px; }
.signal-grid-line { fill: none; stroke: rgba(98, 160, 197, .17); stroke-width: .7; stroke-dasharray: 2 3; }
.signal-card polyline { fill: none; stroke: var(--bearing-cyan); stroke-width: 1.7; vector-effect: non-scaling-stroke; }
.signal-card polyline.ok { stroke: var(--bearing-green); }
.signal-card polyline.warning { stroke: var(--bearing-yellow); }
.signal-card polyline.danger { stroke: var(--bearing-red); }
.signal-card polyline.blue { stroke: #829dff; }
.signal-foot { display: flex; align-items: center; gap: 5px; margin-top: 6px; color: #709cb6; font-size: 9px; }
.signal-foot i { width: 5px; height: 5px; border-radius: 50%; background: var(--bearing-cyan); }
.signal-foot i.ok { background: var(--bearing-green); }
.signal-foot i.warning { background: var(--bearing-yellow); }
.signal-foot i.danger { background: var(--bearing-red); }

.evidence-panel, .action-panel, .parameter-panel { min-height: 0; }
.evidence-list { display: grid; gap: 2px; }
.evidence-item { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 7px; padding: 8px 0; border-bottom: 1px solid rgba(68, 145, 197, .13); }
.evidence-item:last-child { border-bottom: 0; }
.evidence-icon { display: grid; place-items: center; width: 22px; height: 22px; border: 1px solid currentColor; color: var(--bearing-cyan); font: 10px ui-monospace, monospace; }
.evidence-icon.ok { color: var(--bearing-green); }.evidence-icon.warning { color: var(--bearing-yellow); }.evidence-icon.danger { color: var(--bearing-red); }
.evidence-item strong { color: #c9e7f4; font-size: 10px; }.evidence-item p { margin: 2px 0 0; color: #6e9bb3; font-size: 8px; white-space: nowrap; }.evidence-state { font-size: 9px; }.evidence-state.ok { color: var(--bearing-green); }.evidence-state.warning { color: var(--bearing-yellow); }.evidence-state.danger { color: var(--bearing-red); }
.action-banner { display: grid; gap: 3px; padding: 9px; border-left: 3px solid var(--bearing-green); background: rgba(36, 144, 102, .12); }.action-banner.warning { border-color: var(--bearing-yellow); background: rgba(165, 125, 26, .13); }.action-banner.danger { border-color: var(--bearing-red); background: rgba(159, 35, 54, .14); }.action-banner span { color: #72bfaa; font: 8px ui-monospace, monospace; }.action-banner.warning span { color: #dfc16b; }.action-banner.danger span { color: #ee8994; }.action-banner strong { color: #eafaff; font-size: 13px; }
.action-list { display: grid; gap: 8px; margin: 11px 0 0; padding: 0; list-style: none; }.action-list li { display: grid; grid-template-columns: 23px 1fr; gap: 6px; color: #9fc6d9; font-size: 9px; line-height: 1.45; }.action-list b { color: #4bbde3; font: 9px ui-monospace, monospace; }
.parameter-panel { padding-bottom: 8px; }.parameter-table { display: grid; }.parameter-row { display: grid; grid-template-columns: 1fr auto auto; align-items: baseline; gap: 6px; padding: 6px 0; border-bottom: 1px solid rgba(68, 145, 197, .13); color: #83abc1; font-size: 9px; }.parameter-row strong { color: #e6faff; font: 11px ui-monospace, monospace; }.parameter-row em { min-width: 31px; color: #608ca7; font-size: 8px; font-style: normal; }
.bearing-method-note { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 30px; margin-top: 8px; padding: 5px 10px; color: #719cb4; font-size: 9px; }.bearing-method-note span { display: inline-flex; align-items: center; gap: 6px; }.bearing-method-note span:first-child { color: #8decc4; }

@media (max-width: 1200px) { .bearing-workbench { grid-template-columns: 200px minmax(0, 1fr); }.bearing-side-column { grid-column: 1 / -1; grid-template-columns: 1.2fr 1fr 1fr; }.bearing-main-column { grid-column: 2; grid-row: 1; }.bearing-input-panel { grid-row: 1; }.bearing-method-note { flex-wrap: wrap; } }
@media (max-width: 820px) { .bearing-title-strip { align-items: flex-start; flex-direction: column; }.bearing-toolbar { width: 100%; justify-content: flex-end; }.bearing-summary-grid { grid-template-columns: repeat(2, 1fr); }.bearing-workbench { display: flex; flex-direction: column; }.bearing-side-column { display: grid; grid-template-columns: 1fr; }.bearing-result-layout { grid-template-columns: 1fr; }.bearing-gauge-wrap { min-height: 190px; }.signal-grid { grid-template-columns: 1fr; } }
@media (max-width: 520px) { .bearing-diagnosis-screen { padding: 8px; }.bearing-summary-grid { grid-template-columns: 1fr 1fr; }.summary-result { font-size: 13px !important; }.bearing-method-note { display: grid; gap: 5px; }.bearing-toolbar { justify-content: flex-start; flex-wrap: wrap; } }
</style>
