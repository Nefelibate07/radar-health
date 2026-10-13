const { contextBridge } = require('electron')

const port = Number(process.env.BACKEND_PORT || 5000)
const baseUrl = `http://127.0.0.1:${port}`

contextBridge.exposeInMainWorld('radarBackend', Object.freeze({
  baseUrl,
  socketUrl: baseUrl
}))
