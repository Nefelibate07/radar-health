<template>
  <div class="health-dashboard" v-loading="loading">
    <p class="source-note">数据来源：合成演示快照 · /api/health/daily-report</p>
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card class="box-card" header="今日健康指数">
          <div class="gauge-container">
            <el-progress
              type="dashboard"
              :percentage="summary.today_score"
              :color="healthColors"
              :width="200"
            />
            <div class="score-label">
              <p class="status-text" :style="{ color: getStatusColor(summary.today_score) }">
                系统状态：{{ getStatusText(summary.today_score) }}
              </p>
            </div>
          </div>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card class="box-card" header="本周评分统计">
          <el-statistic title="平均健康分" :value="summary.average_score" />
          <div class="history-list">
            <div v-for="day in dailyScores" :key="day.date" class="history-item">
              <span class="day-text">{{ day.display_date }}</span>
              <el-progress
                :percentage="day.score"
                :stroke-width="15"
                :color="healthColors"
                style="width: 70%"
              />
              <el-tag size="small" type="info">{{ day.fault_count }} 次故障</el-tag>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted, defineExpose } from 'vue'
import axios from 'axios'
import { API_PREFIX } from '../../config/backend'

const dailyScores = ref([])
const summary = ref({ today_score: null, average_score: null })
const loading = ref(false)

// 评分颜色梯度
const healthColors = [
  { color: '#f56c6c', percentage: 60 },
  { color: '#e6a23c', percentage: 80 },
  { color: '#67c23a', percentage: 100 },
]

// 获取数据的核心函数
const refreshData = async () => {
  loading.value = true
  try {
    const res = await axios.get(`${API_PREFIX}/health/daily-report`)
    dailyScores.value = res.data.data
    summary.value = res.data.summary
  } catch (error) {
    console.error("加载健康看板失败", error)
  } finally {
    loading.value = false
  }
}

// 辅助函数：状态文字
const getStatusText = (score) => score == null ? '--' : (score >= 60 ? '正常' : score >= 30 ? '故障' : '报废')

const getStatusColor = (score) => {
  if (score >= 60) return '#67c23a'
  if (score >= 30) return '#e6a23c'
  return '#f56c6c'
}

// 暴露给父组件调用
defineExpose({ refreshData })

onMounted(refreshData)
</script>

<style scoped>
.health-dashboard { padding: 20px; }
.gauge-container { text-align: center; padding: 20px 0; }
.score-label { margin-top: -20px; font-weight: bold; }
.history-list { margin-top: 20px; }
.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 15px;
}
.day-text { width: 80px; font-size: 14px; }
</style>
