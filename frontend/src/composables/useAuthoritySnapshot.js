import { computed, onMounted, onUnmounted, ref } from 'vue'
import axios from 'axios'
import { createDashboardSocket } from '../socket/dashboardSocket'
import { API_PREFIX } from '../config/backend'

/**
 * 正式页面唯一实时数据入口。
 * Socket.IO 的 update_dashboard 负载来自后端 ScenarioEngine；本文件不生成
 * 任何默认遥测值，尚未收到快照时统一返回空对象/--。
 */
export function useAuthoritySnapshot() {
  const payload = ref(null)
  const connected = ref(false)
  const lastUpdated = ref('')
  let socket = null

  const data = computed(() => payload.value?.data || {})
  const overview = computed(() => data.value.overview || {})
  const health = computed(() => data.value.health || {})
  const scenarioRecord = computed(() => payload.value?.scenario_record || {})
  const source = computed(() => ({
    source_type: scenarioRecord.value.source_type || health.value.authority_replay?.source_type || null,
    source_file: scenarioRecord.value.source_file || null,
    source_line_no: scenarioRecord.value.source_line_no ?? null,
    source_sequence: scenarioRecord.value.source_sequence ?? null,
    timestamp: scenarioRecord.value.timestamp || null,
    sequence: scenarioRecord.value.sequence ?? null
  }))

  const connect = () => {
    socket = createDashboardSocket({
      onConnect: () => { connected.value = true },
      onDisconnect: () => { connected.value = false },
      onDashboardUpdate: (nextPayload) => {
        if (!nextPayload?.data) return
        payload.value = nextPayload
        lastUpdated.value = nextPayload.scenario_record?.timestamp || new Date().toLocaleString()
      }
    })
  }

  const refresh = async () => {
    const response = await axios.get(`${API_PREFIX}/dashboard`)
    if (response.data?.data) {
      payload.value = response.data
      lastUpdated.value = response.data.scenario_record?.timestamp || new Date().toLocaleString()
    }
    return response.data
  }

  onMounted(connect)
  onUnmounted(() => {
    socket?.disconnect()
    socket = null
  })

  return { payload, connected, lastUpdated, data, overview, health, scenarioRecord, source, refresh }
}

export const snapshotParameters = (health) => Array.isArray(health?.parameters) ? health.parameters : []
export const snapshotSubsystems = (health) => Array.isArray(health?.subsystems) ? health.subsystems : []
export const snapshotStatus = (score) => {
  const n = Number(score)
  if (!Number.isFinite(n)) return '--'
  if (n >= 60) return '正常'
  if (n >= 30) return '故障'
  return '报废'
}

export const formatSnapshotValue = (item) => {
  if (!item || item.value === undefined || item.value === null) return '--'
  return item.display_value ?? String(item.value)
}
