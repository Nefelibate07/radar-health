<template>
  <el-drawer
    v-model="visible"
    title="故障详情"
    size="480px"
    direction="rtl"
    destroy-on-close
    @close="handleClose"
  >
    <div v-if="faultData" class="fault-detail">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="事件ID">{{ faultData.event_id || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="故障时间">{{ faultData.故障时间 || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="严重程度">
          <el-tag :type="faultData.故障程度 === '严重故障' ? 'danger' : 'warning'">
            {{ faultData.故障程度 || 'N/A' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="严重等级">{{ faultData.严重等级 || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="故障设备">{{ faultData.故障设备 || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="故障部件">{{ faultData.故障部件 || 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="故障类型">{{ faultData.故障类型 || 'N/A' }}</el-descriptions-item>
      </el-descriptions>

      <h4 class="section-title">异常参数</h4>
      <el-table
        v-if="faultData.异常参数 && faultData.异常参数.length"
        :data="faultData.异常参数"
        border
        size="small"
        style="margin-bottom: 16px"
      >
        <el-table-column prop="name" label="参数名称" width="140" />
        <el-table-column prop="current" label="当前值" width="90" />
        <el-table-column prop="threshold" label="阈值" width="120" />
        <el-table-column prop="desc" label="说明" show-overflow-tooltip />
      </el-table>
      <p v-else class="empty-tip">无异常参数记录</p>

      <div class="drawer-footer">
        <el-button
          type="primary"
          :icon="Download"
          :loading="exportLoading"
          @click="handleExport"
        >
          导出 DOCX 报告
        </el-button>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import axios from 'axios'
import { faultDetailVisible, currentFaultData, closeFaultDetail } from '../../stores/faultStore'
import { API_PREFIX } from '../../config/backend'

const exportLoading = ref(false)

const visible = computed({
  get: () => faultDetailVisible.value,
  set: (v) => {
    faultDetailVisible.value = v
    if (!v) closeFaultDetail()
  }
})

const faultData = computed(() => currentFaultData.value)

function handleClose() {
  closeFaultDetail()
}

async function handleExport() {
  const id = faultData.value?.error_id
  if (!id) {
    ElMessage.warning('无法导出：缺少故障记录 ID')
    return
  }
  exportLoading.value = true
  try {
    const response = await axios({
      url: `${API_PREFIX}/errors/${id}/export/docx`,
      method: 'GET',
      responseType: 'blob'
    })
    if (response.data.type === 'application/json') {
      const text = await response.data.text()
      const err = JSON.parse(text)
      throw new Error(err.error || '导出失败')
    }
    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `FaultReport_${faultData.value?.event_id || id}.docx`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()
    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 200)
    ElMessage.success('报告导出成功')
  } catch (err) {
    ElMessage.error(err.message || '导出失败')
  } finally {
    exportLoading.value = false
  }
}
</script>

<style scoped>
.fault-detail {
  padding: 0 8px;
}
.section-title {
  margin: 16px 0 8px;
  font-size: 14px;
  color: #303133;
}
.empty-tip {
  margin: 8px 0 16px;
  color: #909399;
  font-size: 13px;
}
.drawer-footer {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}
</style>
