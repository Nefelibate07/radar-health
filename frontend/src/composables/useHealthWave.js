import { onUnmounted, ref } from 'vue'
import { transitionHealth } from '../stores/healthAlgorithmStore.js'

// 兼容旧调用方：只对传入的后端快照值做平滑，不生成随机信号。
const clamp = (value, fallback = 100) => {
  const n = Number(value)
  if (!Number.isFinite(n)) return fallback
  return Math.min(100, Math.max(0, n))
}

const TRANSITION_RATE = 0.3

/**
 * @param {import('vue').Ref<number>|import('vue').ComputedRef<number>} originalScoreRef -
 *   取自持续更新的真实系统健康度（如 Socket.IO 推送）。
 *   本兼容函数只对已收到的后端值做平滑，不补造遥测数据。
 */
export function useHealthWave(originalScoreRef, { tickMs = 400 } = {}) {
  const initial = clamp(originalScoreRef?.value, 100)
  const waveHealth = ref(initial)
  const step = () => {
    const baseline = clamp(originalScoreRef?.value, waveHealth.value)
    waveHealth.value = clamp(transitionHealth(waveHealth.value, baseline, TRANSITION_RATE))

    if (import.meta.env?.DEV) {
      console.debug(
        '[useHealthWave] authority replay',
        '-> waveHealth =', waveHealth.value,
        '(baseline', baseline, ')'
      )
    }
  }

  const timer = setInterval(step, tickMs)
  onUnmounted(() => clearInterval(timer))

  return { waveHealth }
}
