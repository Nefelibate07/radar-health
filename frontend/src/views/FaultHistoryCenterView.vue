<template>
  <section class="fault-screen">
    <header class="screen-header panel">
      <div class="header-left">
        <p class="eyebrow">FAULT TRACE CENTER</p>
        <h1>故障历史中心</h1>
      </div>
      <div class="header-actions">
        <span class="source-badge">合成演示快照</span>
        <el-button class="action-btn ghost" @click="goBack">返回健康页</el-button>
        <el-button class="action-btn ghost" :loading="loading" @click="fetchData(currentPage)">刷新记录</el-button>
      </div>
    </header>

    <div class="kpi-row">
      <article class="kpi-card panel">
        <span>总故障记录</span>
        <strong>{{ total }}</strong>
      </article>
      <article class="kpi-card panel">
        <span>严重故障</span>
        <strong class="danger">{{ severeCount }}</strong>
      </article>
      <article class="kpi-card panel">
        <span>一般故障</span>
        <strong class="warn">{{ generalCount }}</strong>
      </article>
    </div>

    <article class="table-panel panel" v-loading="loading">
      <div class="toolbar">
        <el-select v-model="severityFilter" placeholder="严重程度" size="small" style="width: 140px">
          <el-option label="全部" value="all" />
          <el-option label="严重故障" value="严重故障" />
          <el-option label="一般故障" value="一般故障" />
        </el-select>
      </div>

      <el-table :data="filteredData" stripe border @row-click="handleRowClick" class="fault-table">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="timestamp" label="故障时间" width="180" />
        <el-table-column prop="error_type" label="故障等级" width="120">
          <template #default="scope">
            <el-tag :type="scope.row.error_type === '严重故障' ? 'danger' : 'warning'" effect="dark">
              {{ scope.row.error_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="故障部位" min-width="220">
          <template #default="scope">
            {{ getFaultParts(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="事件号" min-width="160">
          <template #default="scope">
            {{ scope.row.fault_report?.event_id || `FAULT-${scope.row.id}` }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="scope">
            <el-button type="primary" link @click.stop="handleRowClick(scope.row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-container">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          :total="total"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </article>

    <FaultDetailDrawer />
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { API_PREFIX } from '../config/backend'
import { openFaultDetail } from '../stores/faultStore'
import FaultDetailDrawer from './demo/FaultDetailDrawer.vue'

const router = useRouter()

const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const severityFilter = ref('all')

const filteredData = computed(() => {
  if (severityFilter.value === 'all') return tableData.value
  return tableData.value.filter((item) => item.error_type === severityFilter.value)
})

const severeCount = computed(() => tableData.value.filter((item) => item.error_type === '严重故障').length)
const generalCount = computed(() => tableData.value.filter((item) => item.error_type === '一般故障').length)

function getFaultParts(row) {
  const report = row.fault_report || {}
  const parts = []
  if (report.turntable_system) parts.push('转台系统')
  if (report.geodetic_system) parts.push('大地系统')
  if (report.motor_1) parts.push('电机1')
  if (report.motor_2) parts.push('电机2')
  return parts.length ? parts.join('、') : (report.故障部件 || '--')
}

function handleRowClick(row) {
  const report = row.fault_report || {}
  if (!report.event_id && !report.故障程度) {
    report.event_id = `FAULT-${row.id}`
    report.故障时间 = row.timestamp
    report.故障程度 = row.error_type
  }
  report.error_id = row.id
  openFaultDetail(report)
}

const fetchData = async (page = 1) => {
  loading.value = true
  try {
    const res = await axios.get(`${API_PREFIX}/errors`, {
      params: { page, page_size: pageSize.value, sort: 'DESC' }
    })
    tableData.value = res.data?.items || []
    total.value = res.data?.total || 0
  } catch (error) {
    ElMessage.error('故障历史加载失败')
    tableData.value = []
    total.value = 0
    console.error(error)
  } finally {
    loading.value = false
  }
}

const handlePageChange = (page) => {
  currentPage.value = page
  fetchData(page)
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchData(1)
}

const goBack = () => {
  router.push('/health')
}

onMounted(() => fetchData(1))
</script>

<style scoped>
.fault-screen {
  min-height: calc(100vh - 20px);
  padding: 12px;
  color: #daf5ff;
  border: 2px solid #18bfff;
  border-radius: 12px;
  background:
    radial-gradient(circle at 85% 0%, rgba(70, 173, 255, 0.16), transparent 40%),
    linear-gradient(180deg, #05163f 0%, #082966 50%, #051b4f 100%);
  box-shadow: inset 0 0 34px rgba(23, 121, 214, 0.22), 0 0 16px rgba(22, 185, 255, 0.2);
}

.panel {
  border: 1px solid rgba(88, 203, 255, 0.42);
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(8, 36, 90, 0.88), rgba(6, 23, 67, 0.9));
  box-shadow: inset 0 0 16px rgba(29, 150, 255, 0.16);
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
  color: #91e0ff;
  font-size: 11px;
  letter-spacing: 1.6px;
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
  background: #163868;
  color: #caefff;
  border-color: #397ab8;
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

.kpi-row {
  margin-top: 12px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(3, 1fr);
}

.kpi-card {
  padding: 12px;
}

.kpi-card span {
  color: #8dd8f1;
  font-size: 13px;
}

.kpi-card strong {
  display: block;
  margin-top: 6px;
  font-size: 34px;
  color: #f0fbff;
}

.kpi-card strong.warn {
  color: #ffd87a;
}

.kpi-card strong.danger {
  color: #ff8f9e;
}

.table-panel {
  margin-top: 12px;
  padding: 12px;
}

.toolbar {
  margin-bottom: 10px;
  display: flex;
  justify-content: flex-end;
}

.pagination-container {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.fault-table :deep(.el-table__row) {
  cursor: pointer;
}

.fault-table :deep(.el-table) {
  --el-table-bg-color: rgba(8, 29, 72, 0.34);
  --el-table-tr-bg-color: rgba(8, 29, 72, 0.12);
  --el-table-header-bg-color: rgba(15, 52, 118, 0.76);
  --el-table-border-color: rgba(91, 195, 255, 0.2);
  --el-table-text-color: #d7f5ff;
  --el-table-header-text-color: #9fe7ff;
}

@media (max-width: 980px) {
  .screen-header {
    flex-direction: column;
    align-items: flex-start;
  }

  .kpi-row {
    grid-template-columns: 1fr;
  }
}
</style>
