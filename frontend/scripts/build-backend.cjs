const path = require('path')
const fs = require('fs')
const { spawnSync } = require('child_process')

const frontendRoot = path.resolve(__dirname, '..')
const projectRoot = path.resolve(frontendRoot, '..')
const backendRoot = path.join(projectRoot, 'backend')
const outputDir = path.resolve(frontendRoot, process.env.DESKTOP_BACKEND_DIST_DIR || 'backend-dist')
const workDir = path.resolve(frontendRoot, process.env.DESKTOP_BACKEND_WORK_DIR || '.backend-build')
const entry = path.join(backendRoot, 'run.py')
const target = process.env.DESKTOP_TARGET || process.platform

const targetPlatforms = {
  darwin: 'darwin',
  mac: 'darwin',
  win32: 'win32',
  win: 'win32',
  linux: 'linux'
}

const normalizedTarget = targetPlatforms[target]
if (!normalizedTarget) {
  console.error(`[desktop] unsupported DESKTOP_TARGET: ${target}`)
  process.exit(2)
}

if (normalizedTarget !== process.platform) {
  console.error(
    `[desktop] cannot build a ${normalizedTarget} backend on ${process.platform}. ` +
    `Run this command on the target OS; PyInstaller does not cross-compile native executables.`
  )
  process.exit(2)
}

function exists(filePath) {
  try {
    return fs.existsSync(filePath)
  } catch {
    return false
  }
}

function findPython() {
  const candidates = process.platform === 'win32'
    ? [
        process.env.PYTHON,
        path.join(backendRoot, '.venv', 'Scripts', 'python.exe'),
        'python.exe',
        'python'
      ]
    : [
        process.env.PYTHON,
        path.join(backendRoot, 'venv', 'bin', 'python'),
        path.join(backendRoot, '.venv', 'bin', 'python'),
        'python3',
        'python'
      ]

  return candidates.filter(Boolean).find((candidate) => {
    return candidate.includes(path.sep) ? exists(candidate) : true
  })
}

if (!exists(entry)) {
  console.error(`[desktop] backend entry not found: ${entry}`)
  process.exit(1)
}

fs.mkdirSync(outputDir, { recursive: true })
fs.mkdirSync(workDir, { recursive: true })
const pyinstallerConfigDir = path.join(workDir, 'pyinstaller-config')
fs.mkdirSync(pyinstallerConfigDir, { recursive: true })

const python = findPython()
if (!python) {
  console.error('[desktop] Python 3 was not found. Set PYTHON or create backend/.venv first.')
  process.exit(1)
}

const args = [
  '-m', 'PyInstaller',
  '--noconfirm',
  '--clean',
  // PyTorch ships a large set of interdependent macOS dylibs. Keep their
  // package-relative layout intact so dyld can resolve @rpath dependencies.
  '--onedir',
  '--name', 'radar-health-backend',
  '--paths', backendRoot,
  '--distpath', outputDir,
  '--workpath', workDir,
  '--specpath', workDir,
  '--hidden-import', 'app.routes.logs',
  '--hidden-import', 'app.routes.errors',
  '--hidden-import', 'app.routes.health',
  '--hidden-import', 'app.routes.ip_config',
  '--hidden-import', 'app.routes.telemetry',
  '--hidden-import', 'app.routes.debug',
  '--hidden-import', 'app.routes.scenario',
  '--hidden-import', 'app.routes.graph',
  '--hidden-import', 'app.routes.database',
  '--hidden-import', 'app.routes.algorithms',
  '--hidden-import', 'app.routes.radar_reconstruction',
  '--hidden-import', 'app.routes.data_processing',
  '--hidden-import', 'app.routes.fault_diagnosis',
  '--hidden-import', 'app.data_processing',
  '--hidden-import', 'app.fault_diagnosis',
  '--hidden-import', 'app.file_capture',
  // Flask-SocketIO selects the Engine.IO driver through importlib at runtime.
  // PyInstaller cannot infer that dynamic import, so include the explicitly
  // selected cross-platform threading driver and its WebSocket dependency.
  '--hidden-import', 'engineio.async_drivers.threading',
  '--hidden-import', 'engineio.async_drivers._websocket_wsgi',
  '--hidden-import', 'simple_websocket',
  '--collect-submodules', 'simple_websocket',
  '--hidden-import', 'wsproto',
  entry
]

console.log(`[desktop] building backend with ${python}`)
const result = spawnSync(python, args, {
  cwd: backendRoot,
  env: {
    ...process.env,
    PYTHONPATH: backendRoot,
    PYINSTALLER_CONFIG_DIR: pyinstallerConfigDir
  },
  stdio: 'inherit'
})

if (result.error) {
  console.error(`[desktop] failed to start PyInstaller: ${result.error.message}`)
  process.exit(1)
}

if (result.status !== 0) {
  console.error('[desktop] PyInstaller failed. Install it with: python -m pip install pyinstaller')
  process.exit(result.status || 1)
}

console.log(`[desktop] backend binary ready in ${outputDir}`)
