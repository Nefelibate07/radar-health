<template>
    <div class="container">
      <el-card class="box-card">
        <template #header>
          <div class="card-header">
            <div class="title">设备运行日志监控 · 合成演示快照快照 (SQLite + Flask)</div>
            <div class="actions">
              <el-button @click="fetchData(currentPage)">刷新列表</el-button>
            </div>
          </div>
        </template>

        <div class="export-bar">
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
            style="width: 180px; margin-left: 10px;"
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
            style="margin-left: 10px;">
            导出健康评估 Word 报告
          </el-button>
        </div>

        <el-table
          :data="tableData"
          stripe
          border
          v-loading="loading"
          @sort-change="handleSortChange"
          style="width: 100%">

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
      </el-card>
    </div>
  </template>

  <script setup>
  import { ref, onMounted } from 'vue'
  import axios from 'axios'
  import { ElMessage } from 'element-plus'
  import { Download } from '@element-plus/icons-vue'
  import { API_PREFIX } from '../../config/backend'

  const tableData = ref([])
  const total = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(10)
  const loading = ref(false)
  const currentSort = ref('DESC')
  const dateRange = ref([])
  const exportAlgorithm = ref('kmeans')
  const exportLoading = ref(false)

  const API_BASE = API_PREFIX

  // --- 获取列表数据 ---
  const fetchData = async (page) => {
    loading.value = true
    try {
      const response = await axios.get(`${API_BASE}/logs`, {
        params: { page, page_size: pageSize.value, sort: currentSort.value }
      })
      tableData.value = response.data.items
      total.value = response.data.total
    } catch (error) {
      ElMessage.error('获取列表失败')
    } finally {
      loading.value = false
    }
  }

  // --- 核心导出逻辑（普适版本） ---
  const handleExport = async () => {
    if (!dateRange.value || dateRange.value.length < 2) {
      ElMessage.warning('请先选择日期范围')
      return
    }

    const start = dateRange.value[0]
    const end = dateRange.value[1]
    const algo = exportAlgorithm.value
    exportLoading.value = true

    try {
      const response = await axios({
        url: `${API_BASE}/export/docx`,
        method: 'GET',
        params: { start, end, algorithm: algo },
        responseType: 'blob' // 必须是 blob
      })

      // 1. 安全性检查：后端可能返回了错误 JSON 但状态码是 200
      if (response.data.type === 'application/json') {
        const text = await response.data.text()
        const errJson = JSON.parse(text)
        throw new Error(errJson.error || '导出失败')
      }

      // 2. 创建 Blob 对象，强制指定 DOCX 的 MIME 类型
      const blob = new Blob([response.data], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
      })

      // 3. 兼容性下载触发
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `Report_${start.slice(0, 10)}_${algo}.docx`

      // Firefox 必须将元素插入 DOM 树
      link.style.display = 'none'
      document.body.appendChild(link)

      link.click()

      // 4. 延迟清理（解决 Firefox 的文件损坏关键）
      // 立即执行 revoke 可能会导致 Firefox 还没处理完 Blob 内存就释放了
      setTimeout(() => {
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
      }, 200)

      ElMessage.success('报告导出成功')
    } catch (err) {
      console.error('Export Failed:', err)
      ElMessage.error(err.message || '导出失败，请检查网络或后端状态')
    } finally {
      exportLoading.value = false
    }
  }

  // 分页与排序逻辑
  const handleSortChange = ({ prop, order }) => {
    if (prop === 'timestamp') {
      currentSort.value = order === 'ascending' ? 'ASC' : 'DESC'
      currentPage.value = 1
      fetchData(1)
    }
  }
  const handlePageChange = (val) => { fetchData(val) }
  const handleSizeChange = (val) => { pageSize.value = val; fetchData(1) }
  const handleDelete = async (id) => {
    try {
      await axios.delete(`${API_BASE}/logs/${id}`)
      ElMessage.success('删除成功')
      fetchData(currentPage.value)
    } catch { ElMessage.error('删除失败') }
  }

  onMounted(() => fetchData(1))
  </script>

  <style scoped>
  .container { padding: 20px; background-color: #f5f7fa; min-height: 100vh; }
  .card-header { display: flex; justify-content: space-between; align-items: center; }
  .title { font-size: 18px; font-weight: bold; color: #303133; }
  .export-bar { margin-bottom: 20px; padding: 15px; background-color: #fff; border-radius: 4px; border: 1px dashed #409eff; }
  .pagination-container { margin-top: 20px; display: flex; justify-content: flex-end; }
  .box-card { max-width: 1300px; margin: 0 auto; }
  </style>
