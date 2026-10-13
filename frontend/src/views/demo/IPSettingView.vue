<template>
  <div class="ip-settings">
    <el-card header="上位机通信配置">
      <el-form label-width="120px">
        <el-form-item label="当前上位机 IP">
          <el-tag type="info" size="large">{{ currentIp }}</el-tag>
        </el-form-item>

        <el-form-item label="设置新 IP">
          <el-input v-model="newIp" placeholder="例如: 127.0.0.1" style="width: 300px;" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveIp" :loading="saving">确认修改</el-button>
          <el-button @click="fetchCurrentIp">刷新状态</el-button>
        </el-form-item>
      </el-form>

      <div class="tip">
        <el-alert title="安全提示" type="warning" description="修改后，后端将只接收该 IP 发送的 JSON 数据，其他来源将被拒绝。" show-icon />
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_PREFIX } from '../../config/backend'

const currentIp = ref('加载中...')
const newIp = ref('')
const saving = ref(false)

const fetchCurrentIp = async () => {
  const res = await axios.get(`${API_PREFIX}/config/ip`)
  currentIp.value = res.data.current_ip
}

const saveIp = async () => {
  if (!newIp.value) return ElMessage.error('请输入有效IP')
  saving.value = true
  try {
    const response = await axios.post(`${API_PREFIX}/config/ip`, { new_ip: newIp.value })
    ElMessage.success('上位机IP修改成功')
    currentIp.value = response.data?.current_ip || newIp.value
    newIp.value = ''
  } catch (e) {
    ElMessage.error('修改失败')
  } finally {
    saving.value = false
  }
}

onMounted(fetchCurrentIp)
</script>

<style scoped>
.ip-settings { padding: 20px; max-width: 600px; margin: 0 auto; }
.tip { margin-top: 20px; }
</style>
