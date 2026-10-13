<template>
  <div v-show="false"></div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { io } from 'socket.io-client'
import { ElNotification } from 'element-plus'
import { SOCKET_URL } from '../../config/backend'
import { openFaultDetail } from '../../stores/faultStore'

// 连接到 SocketIO 服务端
const socket = io(SOCKET_URL)

onMounted(() => {
  // 监听后端发出的 'fault_alarm' 事件
  socket.on('fault_alarm', (data) => {
    console.log('收到故障推送:', data)

    // 弹出右侧提醒框，点击可查看详情
    ElNotification({
      title: `报警：系统出现${data.故障程度}`,
      message: formatMessage(data),
      type: data.故障程度 === '严重故障' ? 'error' : 'warning',
      duration: 0,
      position: 'top-right',
      onClick: () => {
        openFaultDetail(data)
      }
    })
  })
})

// 格式化展示报警详细内容
const formatMessage = (data) => {
  let msg = ''
  if (data.turntable_system) msg += `转台：${data.turntable_system}；`
  if (data.geodetic_system) msg += `大地系：${data.geodetic_system}；`
  if (data.motor_1) msg += `电机1：${data.motor_1}；`
  if (data.motor_2) msg += `电机2：${data.motor_2}；`
  return msg || '点击查看详情'
}

onUnmounted(() => {
  socket.disconnect()
})
</script>
