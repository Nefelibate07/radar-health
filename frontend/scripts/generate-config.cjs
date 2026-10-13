const path = require('path')
const { spawnSync } = require('child_process')

const frontendRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendRoot, '..')
const script = path.join(projectRoot, 'config', 'build_params.py')
const pythonCandidates = process.platform === 'win32'
  ? [process.env.PYTHON, 'python']
  : [process.env.PYTHON, 'python3', 'python']

const python = pythonCandidates.filter(Boolean).find((candidate) => {
  if (!candidate.includes(path.sep)) return true
  return require('fs').existsSync(candidate)
})

if (!python) {
  console.error('[config] Python 3 was not found; cannot generate subsystems.generated.js')
  process.exit(1)
}

console.log(`[config] generating frontend subsystem config with ${python}`)
const result = spawnSync(python, [script], {
  cwd: projectRoot,
  stdio: 'inherit',
  env: { ...process.env, PYTHONUTF8: '1' }
})

if (result.error) {
  console.error(`[config] failed to start Python: ${result.error.message}`)
  process.exit(1)
}
process.exit(result.status || 0)
