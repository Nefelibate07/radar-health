import { io } from 'socket.io-client'
import { SOCKET_URL } from '../config/backend'

const socketUrl = SOCKET_URL

export function createDashboardSocket({ onConnect, onDisconnect, onDashboardUpdate }) {
  const socket = io(socketUrl, {
    // 后端当前使用 Flask-SocketIO 的 threading 模式，稳定验收链路是
    // polling；如果只声明 websocket，页面会在开发服务器上无法收到推送。
    transports: ['polling']
  })

  socket.on('connect', () => onConnect?.())
  socket.on('disconnect', () => onDisconnect?.())
  socket.on('update_dashboard', (payload) => onDashboardUpdate?.(payload))

  return socket
}
