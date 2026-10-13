import { ref, computed } from 'vue'

// 保留旧页面的导入兼容性，但不再控制或生成任何遥测数据。
// 所有实时值来自后端 ScenarioEngine 的合成演示快照快照。
export const simulationEnabled = ref(true)

export const toggleSimulation = () => {
  simulationEnabled.value = !simulationEnabled.value
}

export const enableSimulation = () => {
  simulationEnabled.value = true
}

export const disableSimulation = () => {
  simulationEnabled.value = false
}

export const simLabel = computed(() => '合成演示快照')

/**
 * Generate a jittered numeric value around a base.
 * When simulation is off, returns the base value unchanged.
 */
export function simNumber(base, amplitude = 5, decimals = 1) {
  return formatNumber(base, decimals)
}

/**
 * Generate an integer value around a base.
 */
export function simInt(base, amplitude = 3) {
  const n = Number(base)
  return Number.isFinite(n) ? Math.round(n) : '--'
}

/**
 * Pick a random status based on probabilities.
 */
export function simStatus(prefer = 'ok') {
  return prefer
}

/**
 * Format a subsystem main parameter with unit, optionally applying simulation noise.
 */
export function simParam(param, amplitude) {
  if (!param) return '--'
  if (param.value === undefined || param.value === null) return '--'
  return `${param.display_value ?? param.value} ${param.unit || ''}`.trim()
}

function inferDecimals(value) {
  if (Math.abs(value) >= 100) return 0
  if (Math.abs(value) >= 10) return 1
  if (Math.abs(value) >= 1) return 2
  return 3
}

function decimalsToAmplitude(value, decimals) {
  if (decimals === 0) return Math.max(1, Math.abs(value) * 0.05)
  if (decimals === 1) return 0.5
  if (decimals === 2) return 0.05
  return 0.005
}

function formatNumber(value, decimals) {
  const factor = Math.pow(10, decimals)
  return Math.round(value * factor) / factor
}
