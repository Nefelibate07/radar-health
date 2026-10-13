// 全局统一的健康度→状态判定与展示映射，取代此前分散在 HealthView/AlertsView/
// SubsystemDetailView 里各自重复、且互相不一致的判定逻辑（部分地方用 60/30，
// AlertsView 之前单独用 90/75 的"优/良/差"）。阈值必须和后端场景引擎的
// _score_status() 保持一致：>=60 正常，>=30 故障，否则报废。
export const HEALTH_STATUS = {
  NORMAL: '正常',
  FAULTY: '故障',
  BROKEN: '报废'
}

export function scoreToStatus(score) {
  const s = Number(score) || 0
  if (s >= 60) return HEALTH_STATUS.NORMAL
  if (s >= 30) return HEALTH_STATUS.FAULTY
  return HEALTH_STATUS.BROKEN
}

// CSS 类名沿用 config/subsystems.generated.js 里 getSubsystemStatusClass() 的既有命名
// (status-ok/status-warn/status-danger)，HealthView/SubsystemDetailView 的卡片样式都是
// 按这个前缀写的选择器——之前这里返回不带前缀的 ok/warn/danger，导致这两个视图里的卡片
// 颜色规则完全没匹配上。
export function statusToClass(status) {
  if (status === HEALTH_STATUS.NORMAL) return 'status-ok'
  if (status === HEALTH_STATUS.FAULTY) return 'status-warn'
  return 'status-danger'
}

export function scoreToClass(score) {
  return statusToClass(scoreToStatus(score))
}
