// 健康页只做显示平滑；真正的算法选择和计算由 /api/health/evaluate 完成。
// 保留统一的键集合，避免前端再次出现 random/e_discrete/sim_switch 这类脱离后端的名称。
export const HEALTH_ALGORITHMS = Object.freeze({
  KMEANS: 'kmeans',
  SOM: 'som',
  STATISTICAL: 'statistical_baseline',
  WEIGHTED_DISTANCE: 'weighted_distance',
})

/**
 * 向目标值渐进过渡(而非跳变)，rate 为每次调用推进的比例(0~1)。
 */
export function transitionHealth(current, target, rate = 0.08) {
  const c = Number.isFinite(Number(current)) ? Number(current) : Number(target) || 0
  const t = Number.isFinite(Number(target)) ? Number(target) : c
  const next = c + (t - c) * rate
  return Math.min(100, Math.max(0, next))
}
