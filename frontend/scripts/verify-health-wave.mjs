// 手动验证脚本(非自动化测试框架，本项目未安装 vitest/jest)：
// 验证 waveHealth 会持续小幅波动，且切换算法时从当前值平滑过渡到新算法的基准值，永不冻结。
// 运行方式：node scripts/verify-health-wave.mjs (在 frontend 目录下)
import { ref } from 'vue'
import { setAlgorithm, HEALTH_ALGORITHMS } from '../src/stores/healthAlgorithmStore.js'
import { useHealthWave } from '../src/composables/useHealthWave.js'

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

const assertClamped = (label, value) => {
  if (!Number.isFinite(value) || value < 0 || value > 100) {
    throw new Error(`[FAIL] ${label}: waveHealth 不是 [0,100] 范围内的有限数字, got ${value}`)
  }
}

async function main() {
  let failed = false
  const originalScore = ref(80)
  const { waveHealth } = useHealthWave(originalScore, { tickMs: 20 })

  // 1) 随机评估：waveHealth 应稳定在原系统健康度(80)附近小幅波动，而不是完全冻结在某个数字上
  setAlgorithm(HEALTH_ALGORITHMS.RANDOM)
  await wait(400)
  assertClamped('随机评估-初始波动', waveHealth.value)
  if (Math.abs(waveHealth.value - 80) > 10) {
    console.error(`[FAIL] 随机评估应在80附近波动, got ${waveHealth.value}`)
    failed = true
  } else {
    console.log(`[OK] 随机评估在80附近波动, 当前 ${waveHealth.value.toFixed(2)}`)
  }

  const samples = []
  for (let i = 0; i < 10; i += 1) {
    await wait(20)
    samples.push(waveHealth.value)
  }
  const distinctSamples = new Set(samples.map((v) => v.toFixed(3))).size
  if (distinctSamples <= 1) {
    console.error('[FAIL] 随机评估模式下 waveHealth 连续多次采样完全相同，波浪图会看起来是冻结的')
    failed = true
  } else {
    console.log(`[OK] 随机评估模式下 waveHealth 持续变化(${distinctSamples}/${samples.length} 个不同取值)`)
  }

  // 2) 原系统健康度变化(80 -> 90)时，随机评估的基准值必须跟随变化
  originalScore.value = 90
  await wait(2000)
  assertClamped('随机评估-基准变化后', waveHealth.value)
  if (Math.abs(waveHealth.value - 90) > 6) {
    console.error(`[FAIL] 随机评估未跟随原系统健康度变化到90附近, got ${waveHealth.value}`)
    failed = true
  } else {
    console.log(`[OK] 随机评估跟随原系统健康度变化到90附近, 当前 ${waveHealth.value.toFixed(2)}`)
  }

  // 3) 模拟切换：从当前值开始平滑过渡到新基准值(90)，不能瞬间跳变，也不能重置为0/100
  const beforeSwitch = waveHealth.value
  setAlgorithm(HEALTH_ALGORITHMS.SIM_SWITCH)
  await wait(20)
  const justAfterSwitch = waveHealth.value
  if (Math.abs(justAfterSwitch - beforeSwitch) > 20) {
    console.error(`[FAIL] 模拟切换起点应从切换前的值(${beforeSwitch})附近平滑过渡，而不是跳变, got ${justAfterSwitch}`)
    failed = true
  } else {
    console.log(`[OK] 模拟切换从原值(${beforeSwitch.toFixed(2)})附近开始过渡，未瞬间跳变(当前 ${justAfterSwitch.toFixed(2)})`)
  }
  if (justAfterSwitch === 0 || justAfterSwitch === 100) {
    console.error('[FAIL] 模拟切换不应重置为0或100')
    failed = true
  }

  let prev = justAfterSwitch
  let monotonicOk = true
  for (let i = 0; i < 40; i += 1) {
    await wait(20)
    assertClamped(`模拟切换-第${i}次采样`, waveHealth.value)
    if (Math.abs(waveHealth.value - prev) > 15) {
      monotonicOk = false
    }
    prev = waveHealth.value
  }
  if (!monotonicOk) {
    console.error('[FAIL] 模拟切换过程中出现异常跳变，不是连续平滑过渡')
    failed = true
  } else {
    console.log('[OK] 模拟切换过程中数值连续变化，无异常跳变')
  }
  if (Math.abs(waveHealth.value - 90) > 6) {
    console.error(`[FAIL] 模拟切换应最终稳定在基准值90附近, got ${waveHealth.value}`)
    failed = true
  } else {
    console.log(`[OK] 模拟切换最终稳定在90附近, 当前 ${waveHealth.value.toFixed(2)}`)
  }

  // 4) e-离散评估：切换后不能停留在旧算法的数值上不动，必须开始向新基准值过渡
  const beforeDiscrete = waveHealth.value
  setAlgorithm(HEALTH_ALGORITHMS.E_DISCRETE)
  await wait(400)
  assertClamped('e-离散评估', waveHealth.value)
  if (Math.abs(waveHealth.value - beforeDiscrete) < 0.01) {
    console.error('[FAIL] e-离散评估切换后 waveHealth 完全没有变化，怀疑仍停留在旧算法数值上')
    failed = true
  } else {
    console.log(`[OK] e-离散评估切换后 waveHealth 开始变化: ${beforeDiscrete.toFixed(2)} -> ${waveHealth.value.toFixed(2)}`)
  }

  if (failed) {
    console.error('\n验证失败，请检查上方 [FAIL] 项。')
    process.exit(1)
  } else {
    console.log('\n全部验证通过。')
    process.exit(0)
  }
}

main().catch((err) => {
  console.error('验证脚本执行出错:', err)
  process.exit(1)
})
