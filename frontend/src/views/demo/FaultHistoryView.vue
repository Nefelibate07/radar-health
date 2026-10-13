<template>
  <div class="fault-history">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <div class="title">故障历史记录 · 合成演示快照</div>
          <el-button @click="fetchData(currentPage)">刷新</el-button>
        </div>
      </template>

      <el-table
        :data="tableData"
        stripe
        border
        v-loading="loading"
        style="width: 100%"
        @row-click="handleRowClick"
      >
        <el-table-column prop="id" label="ID" width="70" align="center" />
        <el-table-column prop="timestamp" label="故障时间" width="180" />
        <el-table-column prop="error_type" label="故障程度" width="110">
          <template #default="scope">
            <el-tag :type="scope.row.error_type === '严重故障' ? 'danger' : 'warning'" size="small">
              {{ scope.row.error_type }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="故障部位">
          <template #default="scope">
            {{ getFaultParts(scope.row) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right" align="center">
          <template #default="scope">
            <el-button type="primary" size="small" link @click.stop="handleRowClick(scope.row)">
              查看详情
            </el-button>
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
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'
import { API_PREFIX } from '../../config/backend'
import { openFaultDetail } from '../../stores/faultStore'

const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)

function getFaultParts(row) {
  const report = row.fault_report || {}
  const parts = []
  if (report.turntable_system) parts.push('转台系')
  if (report.geodetic_system) parts.push('大地系')
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

const fetchData = async (page) => {
  loading.value = true
  try {
    const res = await axios.get(`${API_PREFIX}/errors`, {
      params: { page, page_size: pageSize.value, sort: 'DESC' }
    })
    tableData.value = res.data.items || []
    total.value = res.data.total || 0
  } catch {
    tableData.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function handlePageChange(p) {
  fetchData(p)
}

function handleSizeChange() {
  currentPage.value = 1
  fetchData(1)
}

onMounted(() => fetchData(1))
</script>

<style scoped>
.fault-history {
  padding: 20px;
  min-height: 400px;
}
.box-card {
  max-width: 900px;
  margin: 0 auto;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title {
  font-size: 18px;
  font-weight: bold;
  color: #303133;
}
.pagination-container {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
:deep(.el-table__row) {
  cursor: pointer;
}
</style>
