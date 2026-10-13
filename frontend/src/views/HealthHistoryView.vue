<template>
  <section class="history-screen">
    <header class="screen-header panel-box">
      <div class="header-left">数据总览页</div>
      <h1>历史查询</h1>
      <div class="header-right">
        <span class="source-badge">合成演示快照</span>
        <button @click="goHome">返回首页</button>
      </div>
    </header>

    <div class="main-layout">
      <aside class="left-menu panel-box">
        <button class="menu-btn is-active" @click="goHome">主界面</button>
      </aside>

      <main class="content">
        <section class="workspace-panel panel-box">
          <section class="monitor-panel workspace-card">
            <div class="monitor-header">
              <div class="monitor-title">设备运行日志监控 (SQLite + Flask)</div>
              <div class="monitor-actions">
                <el-button type="primary" @click="fetchData(currentPage)">刷新列表</el-button>
              </div>
            </div>

            <div class="monitor-toolbar">
              <el-date-picker
                v-model="dateRange"
                type="datetimerange"
                range-separator="至"
                start-placeholder="导出开始时间"
                end-placeholder="导出结束时间"
                value-format="YYYY-MM-DD HH:mm:ss"
                :default-time="[new Date(2000, 1, 1, 0, 0, 0), new Date(2000, 1, 1, 23, 59, 59)]"
              />
              <el-select
                v-model="exportAlgorithm"
                placeholder="选择健康评估算法"
                style="width: 180px; margin-left: 10px"
                clearable
              >
                <el-option label="K-Means" value="kmeans" />
                <el-option label="SOM" value="som" />
                <el-option label="统计基线" value="statistical_baseline" />
                <el-option label="加权距离" value="weighted_distance" />
              </el-select>
              <el-button
                type="warning"
                :icon="Download"
                :loading="exportLoading"
                @click="handleExport"
                style="margin-left: 10px"
              >
                导出健康评估 Word 报告
              </el-button>
            </div>

            <el-table
              :data="tableData"
              stripe
              border
              v-loading="loading"
              @sort-change="handleSortChange"
              class="monitor-table"
            >
              <el-table-column prop="id" label="ID" width="70" align="center" />
              <el-table-column prop="timestamp" label="记录时间" width="180" sortable="custom" />

              <el-table-column label="系统状态">
                <el-table-column prop="sys_mode" label="模式" width="90" />
                <el-table-column prop="sys_lock_status" label="锁定状态" width="100">
                  <template #default="scope">
                    <el-tag :type="scope.row.sys_lock_status === '已锁定' ? 'success' : 'warning'">
                      {{ scope.row.sys_lock_status }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table-column>

              <el-table-column label="电机参数">
                <el-table-column prop="m1_temp" label="电机1温度" width="110">
                  <template #default="scope">{{ scope.row.m1_temp }} °C</template>
                </el-table-column>
                <el-table-column prop="m2_temp" label="电机2温度" width="110">
                  <template #default="scope">{{ scope.row.m2_temp }} °C</template>
                </el-table-column>
              </el-table-column>

              <el-table-column label="操作" width="100" fixed="right" align="center">
                <template #default="scope">
                  <el-popconfirm title="确定删除记录吗？" @confirm="handleDelete(scope.row.id)">
                    <template #reference>
                      <el-button type="danger" size="small" link>删除</el-button>
                    </template>
                  </el-popconfirm>
                </template>
              </el-table-column>
            </el-table>

            <div class="pagination-container">
              <el-pagination
                v-model:current-page="currentPage"
                v-model:page-size="pageSize"
                :page-sizes="[10, 20, 50, 100]"
                layout="total, sizes, prev, pager, next, jumper"
                :total="total"
                @size-change="handleSizeChange"
                @current-change="handlePageChange"
              />
            </div>
          </section>
        </section>
      </main>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'
import { API_PREFIX } from '../config/backend'

const router = useRouter()

const tableData = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(10)
const loading = ref(false)
const currentSort = ref('DESC')
const dateRange = ref([])
const exportAlgorithm = ref('kmeans')
const exportLoading = ref(false)

const fetchData = async (page = 1) => {
  loading.value = true
  try {
    const response = await axios.get(`${API_PREFIX}/logs`, {
      params: { page, page_size: pageSize.value, sort: currentSort.value }
    })
    tableData.value = response.data.items || []
    total.value = response.data.total || 0
  } catch {
    ElMessage.error('获取列表失败')
  } finally {
    loading.value = false
  }
}

const handleExport = async () => {
  if (!dateRange.value || dateRange.value.length < 2) {
    ElMessage.warning('请先选择日期范围')
    return
  }

  const [start, end] = dateRange.value
  const algorithm = exportAlgorithm.value
  exportLoading.value = true

  try {
    const response = await axios({
      url: `${API_PREFIX}/export/docx`,
      method: 'GET',
      params: { start, end, algorithm },
      responseType: 'blob'
    })

    if (response.data.type === 'application/json') {
      const text = await response.data.text()
      const errJson = JSON.parse(text)
      throw new Error(errJson.error || '导出失败')
    }

    const blob = new Blob([response.data], {
      type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    })

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `Report_${start.slice(0, 10)}_${algorithm || 'default'}.docx`
    link.style.display = 'none'
    document.body.appendChild(link)
    link.click()

    setTimeout(() => {
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }, 200)

    ElMessage.success('报告导出成功')
  } catch (err) {
    ElMessage.error(err.message || '导出失败，请检查网络或后端状态')
  } finally {
    exportLoading.value = false
  }
}

const handleSortChange = ({ prop, order }) => {
  if (prop === 'timestamp') {
    currentSort.value = order === 'ascending' ? 'ASC' : 'DESC'
    currentPage.value = 1
    fetchData(1)
  }
}

const handlePageChange = (val) => {
  currentPage.value = val
  fetchData(val)
}

const handleSizeChange = (val) => {
  pageSize.value = val
  currentPage.value = 1
  fetchData(1)
}

const handleDelete = async (id) => {
  try {
    await axios.delete(`${API_PREFIX}/logs/${id}`)
    ElMessage.success('删除成功')
    if (tableData.value.length === 1 && currentPage.value > 1) {
      currentPage.value -= 1
    }
    fetchData(currentPage.value)
  } catch {
    ElMessage.error('删除失败')
  }
}

const goHome = () => {
  router.push('/health')
}

onMounted(() => {
  fetchData(1)
})
</script>

<style scoped>
.history-screen {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  min-height: calc(100vh - 20px);
  color: #bdefff;
  background: linear-gradient(180deg, #031042 0%, #072d79 45%, #03185a 100%);
  border: 2px solid #0cbdf7;
  box-shadow: inset 0 0 36px rgba(23, 120, 214, 0.24), 0 0 18px rgba(21, 177, 255, 0.24);
}

.history-screen::before {
  content: "";
  position: absolute;
  inset: 0;
  z-index: -1;
  background-image:
    linear-gradient(rgba(93, 180, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(93, 180, 255, 0.08) 1px, transparent 1px);
  background-size: 40px 40px;
}

.panel-box {
  border: 1px solid rgba(45, 197, 255, 0.55);
  background: linear-gradient(180deg, rgba(8, 34, 90, 0.88), rgba(4, 20, 63, 0.88));
  border-radius: 10px;
  backdrop-filter: blur(2px);
  position: relative;
}

.panel-box::after {
  content: "";
  position: absolute;
  inset: 5px;
  border: 1px solid rgba(99, 194, 255, 0.12);
  border-radius: 8px;
  pointer-events: none;
}

.screen-header {
  padding: 10px 14px;
  display: grid;
  grid-template-columns: 120px 1fr 330px;
  align-items: center;
}

.screen-header h1 {
  margin: 0;
  text-align: center;
  font-size: 42px;
  color: #edf8ff;
  text-shadow: 0 0 12px rgba(131, 220, 255, 0.32);
}

.header-left {
  font-size: 14px;
}

.header-right {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.header-right button {
  border: 1px solid #35bcff;
  background: #0f3e82;
  color: #c7f5ff;
  padding: 6px 10px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.header-right button:hover {
  box-shadow: 0 0 12px rgba(98, 209, 255, 0.35);
  transform: translateY(-1px);
}

.sim-toggle {
  padding: 6px 10px;
  border-radius: 6px;
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

.main-layout {
  margin-top: 8px;
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 8px;
}

.left-menu {
  padding: 10px;
  display: grid;
  gap: 8px;
  align-content: start;
}

.menu-btn {
  border: 2px solid #4aaeff;
  background: linear-gradient(180deg, #0d2f72, #102d6a);
  color: #d1ecff;
  font-size: 30px;
  padding: 10px 8px;
  border-radius: 6px;
  transition: all 0.2s ease;
}

.menu-btn:hover {
  border-color: #7ce9ff;
  box-shadow: 0 0 14px rgba(110, 225, 255, 0.25);
  transform: translateY(-1px);
}

.menu-btn.is-active {
  border-color: #89f0ff;
  color: #effbff;
  background: linear-gradient(180deg, rgba(53, 120, 228, 0.9), rgba(26, 72, 164, 0.95));
  box-shadow: inset 0 0 14px rgba(146, 235, 255, 0.16), 0 0 16px rgba(91, 220, 255, 0.28);
}

.content {
  display: grid;
  gap: 8px;
}

.workspace-panel {
  padding: 12px;
}

.workspace-card {
  position: relative;
  border-radius: 10px;
  border: 1px solid rgba(73, 191, 255, 0.24);
  background: linear-gradient(180deg, rgba(11, 39, 95, 0.74), rgba(7, 24, 67, 0.82));
  box-shadow: inset 0 0 16px rgba(76, 171, 255, 0.08), 0 0 8px rgba(33, 128, 218, 0.08);
  padding: 12px;
}

.workspace-card::after {
  content: "";
  position: absolute;
  inset: 4px;
  border-radius: 8px;
  border: 1px solid rgba(97, 202, 255, 0.08);
  pointer-events: none;
}

.monitor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.monitor-title {
  font-size: 18px;
  color: #d8f4ff;
}

.monitor-toolbar {
  display: flex;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  gap: 8px;
}

.monitor-table {
  width: 100%;
}

.pagination-container {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

@media (max-width: 1200px) {
  .main-layout {
    grid-template-columns: 1fr;
  }

  .screen-header {
    grid-template-columns: 1fr;
    gap: 10px;
  }

  .screen-header h1 {
    text-align: left;
    font-size: 30px;
  }

  .header-right {
    justify-content: flex-start;
  }
}
</style>
