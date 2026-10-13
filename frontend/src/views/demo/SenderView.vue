<template>
  <div style="padding: 20px; font-family: Arial, sans-serif;">
    <h2>测控系统数据传输测试</h2>

    <button @click="sendTelemetry" style="padding: 10px 20px; cursor: pointer;">
      返回当前协议回放快照 (JSON)
    </button>

    <div v-if="statusMsg" style="margin-top: 20px; color: blue;">
      {{ statusMsg }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import axios from 'axios'
import { API_PREFIX } from '../../config/backend'

const statusMsg = ref('')

// 推荐的 JS 时间格式化方法
const now = new Date();
const timestamp = now.getFullYear() + '-' +
                 String(now.getMonth() + 1).padStart(2, '0') + '-' +
                 String(now.getDate()).padStart(2, '0') + ' ' +
                 String(now.getHours()).padStart(2, '0') + ':' +
                 String(now.getMinutes()).padStart(2, '0') + ':' +
                 String(now.getSeconds()).padStart(2, '0');
// 结果示例: 2026-02-24 05:47:56

const sendTelemetry = async () => {
  const telemetryData = { source: 'authority_replay' }

  try {
    statusMsg.value = "正在发送..."
    const response = await axios.post(`${API_PREFIX}/send-item`, telemetryData)
    statusMsg.value = `服务器响应: ${JSON.stringify(response.data)}`
    console.log("发送成功内容:", telemetryData)
  } catch (error) {
    statusMsg.value = "发送失败，请检查后端是否开启及跨域设置"
    console.error(error)
  }
}
</script>
