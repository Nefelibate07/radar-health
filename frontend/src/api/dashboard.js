import http from './http'

export function sendTelemetry(payload) {
  return http.post('/api/send-item', payload)
}
