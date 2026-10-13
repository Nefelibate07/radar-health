import { ref } from 'vue'
import { sendTelemetry } from '../api/dashboard'
import { createDashboardSocket } from '../socket/dashboardSocket'

export function useDashboard() {
  const isConnected = ref(false)
  const isSending = ref(false)
  const dashboardData = ref(null)
  const errorMessage = ref('')
  const lastUpdated = ref('')

  let socket = null

  const connectSocket = () => {
    socket = createDashboardSocket({
      onConnect: () => {
        isConnected.value = true
        errorMessage.value = ''
      },
      onDisconnect: () => {
        isConnected.value = false
      },
      onDashboardUpdate: (payload) => {
        dashboardData.value = payload
        lastUpdated.value = new Date().toLocaleString()
      }
    })
  }

  const disconnectSocket = () => {
    if (socket) {
      socket.disconnect()
      socket = null
    }
  }

  const triggerTelemetry = async () => {
    isSending.value = true
    errorMessage.value = ''
    try {
      await sendTelemetry({ test: 'trigger' })
    } catch (error) {
      errorMessage.value = error?.message || 'Request failed'
    } finally {
      isSending.value = false
    }
  }

  return {
    isConnected,
    isSending,
    dashboardData,
    errorMessage,
    lastUpdated,
    connectSocket,
    disconnectSocket,
    triggerTelemetry
  }
}
