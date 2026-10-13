<template>
  <section class="ip-screen">
    <header class="screen-header">
      <div class="title-block">
        <span class="eyebrow">NETWORK CONTROL</span>
        <h1>数据路径配置</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">真实文件与模拟文件均可配置</span>
        <button class="head-btn secondary" @click="goMain">返回主界面</button>
        <button class="head-btn" :disabled="loading" @click="fetchPaths">
          {{ loading ? '读取中...' : '刷新路径' }}
        </button>
        <button class="head-btn" :disabled="captureBusy" @click="testCapture">测试读取</button>
        <button v-if="!captureStatus.running" class="head-btn capture-btn" :disabled="captureBusy" @click="startCapture">启动抓取</button>
        <button v-else class="head-btn stop-btn" :disabled="captureBusy" @click="stopCapture">停止抓取</button>
      </div>
    </header>

    <div class="screen-grid">
      <article class="panel current-panel">
        <h2>数据抓取位置</h2>
        <div class="current-ip-box">
          <label>当前抓取模式</label>
          <div class="ip-value">{{ form.capture_mode }}</div>
          <p class="hint">真实模式从文件目录逐行读取，回放模式使用项目协议缓存</p>
          <label>真实数据文件目录</label>
          <div class="path-value">{{ form.capture_input_dir || '未配置' }}</div>
          <label>模拟数据文件目录</label>
          <div class="path-value">{{ form.generator_output_dir || '未配置' }}</div>
        </div>
      </article>

      <article class="panel form-panel">
        <h2>文件与数据库路径</h2>
        <form class="ip-form" @submit.prevent="savePaths">
          <label>数据抓取模式</label>
          <select v-model="form.capture_mode"><option value="replay">协议回放</option><option value="file_capture">文件抓取</option><option value="file_generator">模拟生成文件</option></select>
          <label for="capture-input">真实数据文件目录</label>
          <div class="input-row">
            <input id="capture-input" v-model.trim="form.capture_input_dir" type="text" placeholder="例如：/data/radar/send" />
          </div>
          <label for="generator-output">模拟数据文件目录</label>
          <div class="input-row">
            <input id="generator-output" v-model.trim="form.generator_output_dir" type="text" placeholder="例如：/tmp/radar-capture" />
          </div>
          <label for="health-db">健康数据库位置</label>
          <div class="input-row"><input id="health-db" v-model.trim="form.health_database_path" type="text" placeholder="默认使用 backend/data/app.db" /></div>
          <label for="fault-db">故障数据库位置</label>
          <div class="input-row"><input id="fault-db" v-model.trim="form.fault_database_path" type="text" placeholder="默认使用 backend/data/app.db" /></div>
          <label for="file-pattern">文件匹配规则</label>
          <div class="input-row"><input id="file-pattern" v-model.trim="form.file_pattern" type="text" placeholder="*.txt,*.asc" /></div>
          <div class="input-row">
            <button type="submit" class="primary-btn" :disabled="saving">
              {{ saving ? '保存中...' : '保存路径配置' }}
            </button>
          </div>
          <p class="form-tip">路径设置保存到本地配置；数据库当前仍由 SQLite 统一管理，后续可替换为专业数据库。</p>
        </form>

        <div class="status-strip" :class="messageType" v-if="statusMessage">
          {{ statusMessage }}
        </div>
      </article>

      <article class="panel info-panel">
        <h2>安全提示</h2>
        <ul class="tips">
          <li>目录抓取按文件名和行号追踪，便于回溯问题。</li>
          <li>健康数据库只保存健康度，不保存全部原始参数。</li>
          <li>故障数据库同时保存故障参数和故障分析结果。</li>
        </ul>
      </article>
      <article class="panel capture-panel">
        <h2>实时抓取状态</h2>
        <div class="capture-grid">
          <div><span>状态</span><strong>{{ captureStatus.running ? '运行中' : '未运行' }}</strong></div>
          <div><span>有效 演示快照</span><strong>{{ captureStatus.valid_f104_rows }}</strong></div>
          <div><span>已摄取</span><strong>{{ captureStatus.rows_ingested }}</strong></div>
          <div><span>当前行号</span><strong>{{ captureStatus.line_no }}</strong></div>
        </div>
        <p class="capture-file">{{ captureStatus.file || '尚未读取文件' }}</p>
        <p v-if="captureStatus.last_error" class="error-text">{{ captureStatus.last_error }}</p>
        <p v-if="captureMessage" class="form-tip">{{ captureMessage }}</p>
      </article>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_PREFIX } from '../config/backend'

const router = useRouter()
const form = ref({ capture_mode: 'replay', capture_input_dir: '', generator_output_dir: '', health_database_path: '', fault_database_path: '', file_pattern: '*.txt,*.asc', poll_interval_seconds: 1 })
const saving = ref(false)
const loading = ref(false)
const statusMessage = ref('')
const messageType = ref('')
const captureStatus = ref({ running: false, valid_f104_rows: 0, rows_ingested: 0, line_no: 0, file: null, last_error: null })
const captureBusy = ref(false)
const captureMessage = ref('')

const setStatus = (type, message) => {
  messageType.value = type
  statusMessage.value = message
}

const fetchPaths = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_PREFIX}/config/paths`)
    form.value = { ...form.value, ...(res.data?.data || {}) }
    setStatus('success', '已读取当前路径配置')
  } catch (error) {
    setStatus('error', '读取路径失败')
    ElMessage.error('读取路径失败')
    console.error('fetchCurrentIp failed', error)
  } finally {
    loading.value = false
  }
}

const savePaths = async () => {
  saving.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/config/paths`, form.value)
    // 后端会将部分配置规范化（例如轮询间隔），页面立即采用服务端最终值。
    if (response.data?.data) form.value = { ...form.value, ...response.data.data }
    setStatus('success', '路径配置保存成功')
    ElMessage.success('路径配置已保存')
  } catch (error) {
    setStatus('error', '保存路径失败，请检查后端服务状态')
    ElMessage.error('保存失败')
    console.error('saveIp failed', error)
  } finally {
    saving.value = false
  }
}

const refreshCaptureStatus = async () => {
  try {
    const response = await axios.get(`${API_PREFIX}/capture/status`)
    captureStatus.value = { ...captureStatus.value, ...(response.data?.data || {}) }
  } catch (error) { console.error('capture status failed', error) }
}

const testCapture = async () => {
  captureBusy.value = true
  try {
    const inputDir = form.value.capture_mode === 'file_generator' ? form.value.generator_output_dir : form.value.capture_input_dir
    const response = await axios.post(`${API_PREFIX}/capture/test-read`, { input_dir: inputDir, pattern: form.value.file_pattern })
    const data = response.data?.data || {}
    captureMessage.value = `测试完成：找到 ${data.files || data.file_count || 0} 个文件，解码器映射 ${data.decoder?.unique_mapped_parameter_count || 0} 个字段`
  } catch (error) {
    captureMessage.value = error.response?.data?.error || '测试读取失败'
  } finally { captureBusy.value = false }
}

const startCapture = async () => {
  captureBusy.value = true
  try {
    const inputDir = form.value.capture_mode === 'file_generator' ? form.value.generator_output_dir : form.value.capture_input_dir
    const response = await axios.post(`${API_PREFIX}/capture/start`, { input_dir: inputDir, generator_output_dir: form.value.generator_output_dir, mode: form.value.capture_mode, pattern: form.value.file_pattern, interval: form.value.poll_interval_seconds })
    captureStatus.value = { ...captureStatus.value, ...(response.data?.data || {}) }
    captureMessage.value = '已启动：后端将直接跟读原始文本并更新健康快照'
  } catch (error) { captureMessage.value = error.response?.data?.error || '启动抓取失败' }
  finally { captureBusy.value = false }
}

const stopCapture = async () => {
  captureBusy.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/capture/stop`)
    captureStatus.value = { ...captureStatus.value, ...(response.data?.data || {}) }
    captureMessage.value = '已停止实时抓取'
  } catch (error) { captureMessage.value = error.response?.data?.error || '停止抓取失败' }
  finally { captureBusy.value = false }
}

const goMain = () => {
  router.push('/health')
}

onMounted(async () => { await fetchPaths(); await refreshCaptureStatus(); setInterval(refreshCaptureStatus, 1000) })
</script>

<style scoped>
.ip-screen {
  position: relative;
  min-height: calc(100vh - 32px);
  padding: 16px;
  color: #d9f6ff;
  border: 1px solid rgba(77, 201, 255, 0.4);
  border-radius: 12px;
  background:
    radial-gradient(900px 420px at 10% -5%, rgba(69, 155, 255, 0.16), transparent 65%),
    radial-gradient(700px 320px at 100% 0%, rgba(46, 218, 255, 0.12), transparent 65%),
    linear-gradient(180deg, #06163d, #08265f 52%, #071c4f);
  box-shadow:
    inset 0 0 26px rgba(34, 157, 255, 0.18),
    0 0 16px rgba(25, 133, 236, 0.18);
  overflow: hidden;
}

.ip-screen::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(101, 193, 255, 0.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(101, 193, 255, 0.06) 1px, transparent 1px);
  background-size: 28px 28px;
}

.screen-header {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(101, 209, 255, 0.28);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(16, 50, 106, 0.85), rgba(8, 31, 77, 0.88));
  box-shadow: inset 0 0 16px rgba(58, 171, 255, 0.12);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.title-block {
  display: grid;
  gap: 2px;
}

.eyebrow {
  color: #8ddfff;
  font-size: 11px;
  letter-spacing: 1.8px;
}

.title-block h1 {
  margin: 0;
  font-size: 28px;
  letter-spacing: 2px;
  color: #eefbff;
  text-shadow: 0 0 10px rgba(109, 217, 255, 0.24);
}

.head-btn {
  height: 40px;
  padding: 0 14px;
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

.head-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 12px rgba(89, 205, 255, 0.28);
}

.head-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.capture-btn { border-color: #5be4b0; background: linear-gradient(180deg, #187b6f, #0f554d); }
.stop-btn { border-color: #ff927e; background: linear-gradient(180deg, #9e3c52, #70263d); }
.capture-panel { grid-column: 1 / -1; }
.capture-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.capture-grid div { padding: 12px; border: 1px solid rgba(101, 209, 255, 0.24); border-radius: 8px; background: rgba(6, 28, 72, 0.55); }
.capture-grid span { display: block; color: #8ddfff; font-size: 12px; }
.capture-grid strong { display: block; margin-top: 5px; color: #eefbff; font-size: 20px; }
.capture-file { overflow: hidden; color: #b9e9fa; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
.error-text { color: #ff9b91; }

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

.screen-grid {
  position: relative;
  margin-top: 12px;
  display: grid;
  grid-template-columns: 1.1fr 1.5fr;
  gap: 12px;
}

.panel {
  position: relative;
  border-radius: 10px;
  border: 1px solid rgba(95, 205, 255, 0.28);
  background: linear-gradient(180deg, rgba(8, 32, 79, 0.9), rgba(7, 22, 58, 0.9));
  box-shadow:
    inset 0 0 18px rgba(44, 164, 255, 0.14),
    0 0 8px rgba(31, 127, 231, 0.12);
  padding: 14px;
}

.panel::after {
  content: "";
  position: absolute;
  inset: 6px;
  border: 1px solid rgba(101, 205, 255, 0.12);
  border-radius: 8px;
  pointer-events: none;
}

.panel h2 {
  margin: 0 0 12px;
  display: inline-flex;
  align-items: center;
  height: 30px;
  padding: 0 12px;
  border-radius: 6px;
  color: #a7eeff;
  font-size: 14px;
  border: 1px solid rgba(100, 207, 255, 0.25);
  background: linear-gradient(180deg, rgba(24, 74, 150, 0.95), rgba(15, 46, 104, 0.95));
}

.current-panel {
  min-height: 220px;
}

.current-ip-box {
  display: grid;
  gap: 10px;
  align-content: start;
  min-height: 150px;
  padding: 14px;
  border-radius: 8px;
  border: 1px solid rgba(100, 207, 255, 0.14);
  background: rgba(7, 25, 66, 0.45);
}

.current-ip-box label {
  color: #9bdff7;
  font-size: 13px;
}

.ip-value {
  min-height: 54px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid rgba(110, 216, 255, 0.24);
  background: linear-gradient(180deg, rgba(20, 67, 133, 0.4), rgba(11, 36, 83, 0.35));
  color: #e6fbff;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 1px;
  text-shadow: 0 0 10px rgba(117, 220, 255, 0.2);
}

.hint {
  margin: 0;
  color: #86c7df;
  font-size: 12px;
}

.form-panel {
  min-height: 220px;
}

.ip-form {
  display: grid;
  gap: 10px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid rgba(110, 216, 255, 0.14);
  background: rgba(7, 23, 58, 0.45);
}

.ip-form label {
  font-size: 13px;
  color: #9edcf3;
}

.input-row {
  display: grid;
  grid-template-columns: 1fr 140px;
  gap: 10px;
}

.input-row input {
  height: 42px;
  padding: 0 12px;
  border-radius: 8px;
  border: 1px solid rgba(111, 212, 255, 0.22);
  background: rgba(8, 26, 64, 0.82);
  color: #dcf7ff;
  outline: none;
  transition: 0.2s ease;
}

.input-row input::placeholder {
  color: #6fa6bf;
}

.input-row input:focus {
  border-color: rgba(137, 228, 255, 0.5);
  box-shadow: 0 0 0 3px rgba(74, 167, 255, 0.12);
}

.primary-btn {
  height: 42px;
  border-radius: 8px;
  border: 1px solid rgba(110, 216, 255, 0.35);
  background: linear-gradient(180deg, #2d7ed3, #1b4e97);
  color: #effcff;
  font-weight: 600;
  cursor: pointer;
  transition: 0.2s ease;
}

.primary-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 0 14px rgba(92, 201, 255, 0.26);
}

.primary-btn:disabled {
  opacity: 0.65;
  cursor: not-allowed;
}

.form-tip {
  margin: 0;
  color: #7fc2dc;
  font-size: 12px;
}

.status-strip {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid rgba(111, 212, 255, 0.12);
  font-size: 13px;
}

.status-strip.success {
  color: #77ffd2;
  background: rgba(20, 106, 78, 0.2);
  border-color: rgba(108, 255, 209, 0.16);
}

.status-strip.warning {
  color: #ffe28e;
  background: rgba(138, 102, 12, 0.16);
  border-color: rgba(255, 226, 142, 0.14);
}

.status-strip.error {
  color: #ff9aa8;
  background: rgba(115, 22, 38, 0.18);
  border-color: rgba(255, 154, 168, 0.14);
}

.info-panel {
  grid-column: 1 / -1;
}

.tips {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
  color: #b8ebfb;
  font-size: 13px;
}

@media (max-width: 960px) {
  .screen-grid {
    grid-template-columns: 1fr;
  }

  .info-panel {
    grid-column: auto;
  }

  .input-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 640px) {
  .screen-header {
    flex-direction: column;
    align-items: stretch;
  }

  .header-actions {
    width: 100%;
    flex-direction: column;
  }

  .head-btn {
    width: 100%;
  }

  .title-block h1 {
    font-size: 22px;
  }

  .ip-value {
    font-size: 18px;
    word-break: break-all;
  }
}
</style>
