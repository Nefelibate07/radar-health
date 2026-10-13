const path = require('path')
const fs = require('fs')
const http = require('http')
const net = require('net')
const { spawn } = require('child_process')
const { app, BrowserWindow, dialog } = require('electron')

// Allow isolated smoke runs and portable deployments to keep runtime files
// outside the default macOS Application Support directory.
if (process.env.RADAR_USER_DATA_DIR) {
  app.setPath('userData', path.resolve(process.env.RADAR_USER_DATA_DIR))
}

const isDev = !!process.env.VITE_DEV_SERVER_URL
const BACKEND_HOST = '127.0.0.1'
let backendPort = Number(process.env.BACKEND_PORT || 5000)
let backendProcess = null
let quitting = false

// macOS can temporarily reject a child-process creation when the process
// table or file-descriptor limit is under pressure.  A packaged desktop app
// should give the OS a short opportunity to recover instead of treating the
// first EAGAIN as a permanent backend failure.
const RETRYABLE_SPAWN_CODES = new Set(['EAGAIN', 'EMFILE', 'ENFILE'])
const BACKEND_SPAWN_MAX_ATTEMPTS = 8
const BACKEND_SPAWN_INITIAL_DELAY_MS = 250
// 首次启动可能同时初始化 SQLite、读取回放缓存并加载模型。给后端充足的
// 初始化时间，页面本身会在未就绪时显示连接状态，不应因 30 秒阈值过早判失败。
const BACKEND_READINESS_TIMEOUT_MS = 90000

function log(...args) {
  console.log('[electron]', ...args)
}

function resolveDistIndex() {
  // In packaged app: resources/app/dist/index.html
  // In dev: project-root/dist/index.html
  const candidates = [
    path.join(__dirname, '..', 'dist', 'index.html'),
    path.join(process.resourcesPath, 'app', 'dist', 'index.html'),
    path.join(app.getAppPath(), 'dist', 'index.html')
  ]
  for (const p of candidates) {
    if (fs.existsSync(p)) return p
  }
  return candidates[0]
}

function fileExists(filePath) {
  try {
    return fs.statSync(filePath).isFile()
  } catch {
    return false
  }
}

function resolvePython(projectRoot, backendRoot = path.join(projectRoot, 'backend')) {
  const candidates = process.platform === 'win32'
    ? [
        path.join(backendRoot, '.venv', 'Scripts', 'python.exe'),
        'python.exe',
        'python'
      ]
    : [
        path.join(backendRoot, 'venv', 'bin', 'python'),
        path.join(backendRoot, '.venv', 'bin', 'python'),
        'python3',
        'python'
      ]

  return candidates.find((candidate) => candidate.includes(path.sep) ? fileExists(candidate) : true)
}

function resolveBackendCommand() {
  const dataDir = path.join(app.getPath('userData'), 'data')

  if (app.isPackaged) {
    const resourcesRoot = process.resourcesPath
    const executableName = process.platform === 'win32'
      ? 'radar-health-backend.exe'
      : 'radar-health-backend'
    const backendDistRoot = path.join(resourcesRoot, 'backend-dist')
    const bundledCandidates = [
      path.join(backendDistRoot, executableName),
      path.join(backendDistRoot, executableName.replace(/\.exe$/i, ''), executableName)
    ]
    const bundledExecutable = bundledCandidates.find(fileExists)

    if (fileExists(bundledExecutable)) {
      return {
        command: bundledExecutable,
        args: [],
        cwd: resourcesRoot,
        projectRoot: resourcesRoot,
        dataDir
      }
    }

    const sourceRoot = path.join(resourcesRoot, 'backend-source')
    const sourceEntry = path.join(sourceRoot, 'run.py')
    if (fileExists(sourceEntry)) {
      return {
        command: resolvePython(resourcesRoot, sourceRoot),
        args: [sourceEntry],
        cwd: sourceRoot,
        projectRoot: resourcesRoot,
        dataDir
      }
    }

    return null
  }

  const projectRoot = path.resolve(__dirname, '..', '..')
  const backendRoot = path.join(projectRoot, 'backend')
  return {
    command: resolvePython(projectRoot, backendRoot),
    args: [path.join(backendRoot, 'run.py')],
    cwd: backendRoot,
    projectRoot,
    dataDir: path.join(backendRoot, 'data')
  }
}

function hasTcpListener(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: BACKEND_HOST, port })
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      socket.destroy()
      resolve(value)
    }

    socket.once('connect', () => finish(true))
    socket.once('error', () => finish(false))
    socket.setTimeout(300, () => finish(false))
  })
}

async function isPortAvailable(port) {
  // On macOS, a wildcard listener can coexist with a loopback bind when
  // SO_REUSEPORT is involved.  A bind-only check would therefore claim that
  // an occupied port is free, and the renderer could connect to that other
  // service.  Probe for an existing TCP listener before trying the bind.
  if (await hasTcpListener(port)) return false

  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.listen(port, BACKEND_HOST, () => {
      server.close(() => resolve(true))
    })
  })
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer()
    server.once('error', reject)
    server.listen(0, BACKEND_HOST, () => {
      const port = server.address().port
      server.close(() => resolve(port))
    })
  })
}

async function selectBackendPort() {
  if (await isPortAvailable(backendPort)) return backendPort

  const requestedPort = backendPort
  backendPort = await findFreePort()
  log('backend port occupied, selected another port', {
    requestedPort,
    selectedPort: backendPort
  })
  return backendPort
}

async function startBackend() {
  const backend = resolveBackendCommand()
  if (!backend || !backend.command) {
    dialog.showErrorBox(
      '后端启动失败',
      '未找到随应用打包的后端程序，也未找到可用的 Python。\n' +
        '请先在目标系统运行 npm run desktop:backend:build，或安装 Python 3.12+ 后重试。'
    )
    return Promise.resolve(false)
  }

  await selectBackendPort()
  process.env.BACKEND_PORT = String(backendPort)

  const env = {
    ...process.env,
    PROJECT_ROOT: backend.projectRoot,
    RADAR_DATA_DIR: backend.dataDir,
    HOST: BACKEND_HOST,
    PORT: String(backendPort),
    FLASK_DEBUG: '0'
  }

  // Packaged apps keep the shipped models read-only in Resources.  The
  // backend still writes retrained models to RADAR_DATA_DIR/models; this
  // variable is only a fallback for the initial load in a clean installation.
  if (app.isPackaged) {
    const bundledModelDir = path.join(process.resourcesPath, 'backend-models')
    if (fileExists(path.join(bundledModelDir, 'health_kmeans.json'))) {
      env.RADAR_BUNDLED_MODEL_DIR = bundledModelDir
    }
    const bundledRadarModelDir = path.join(bundledModelDir, 'radar_gat')
    if (fileExists(path.join(bundledRadarModelDir, 'radar_gat_health_best.pt'))) {
      env.RADAR_BUNDLED_RADAR_MODEL_DIR = bundledRadarModelDir
    }
    const bundledRadarBaselineDir = path.join(bundledModelDir, 'radar_baselines')
    if (fileExists(path.join(bundledRadarBaselineDir, 'radar_health_baseline_comparison.json'))) {
      env.RADAR_BUNDLED_RADAR_BASELINE_DIR = bundledRadarBaselineDir
    }
    const bundledDepthMttdDir = path.join(bundledModelDir, 'radar_gat_depth_sweep')
    if (fileExists(path.join(bundledDepthMttdDir, 'radar_gat_depth_mttd.json'))) {
      env.RADAR_BUNDLED_RADAR_DEPTH_MTTD_DIR = bundledDepthMttdDir
    }
    const bundledDemoDir = path.join(process.resourcesPath, 'mcs-health-demo')
    if (fileExists(path.join(bundledDemoDir, 'test.jsonl'))) {
      env.RADAR_BUNDLED_DEMO_DIR = bundledDemoDir
    }
  }

  log('starting backend', {
    command: backend.command,
    cwd: backend.cwd,
    projectRoot: backend.projectRoot,
    dataDir: backend.dataDir,
    packaged: app.isPackaged
  })

  let child
  try {
    child = await spawnBackendWithRetry(backend, env)
  } catch (error) {
    log('backend process error', error)
    dialog.showErrorBox('后端启动失败', `${error.message}\n\n启动命令：${backend.command}`)
    return false
  }

  if (!child) return false

  backendProcess = child

  backendProcess.once('error', (error) => {
    log('backend process error', error)
    dialog.showErrorBox('后端启动失败', `${error.message}\n\n启动命令：${backend.command}`)
  })
  backendProcess.once('exit', (code, signal) => {
    log('backend process exited', { code, signal })
    backendProcess = null
    if (!quitting && code !== 0) {
      dialog.showErrorBox('后端已退出', `后端进程异常退出（code=${code}, signal=${signal || 'none'}）。`)
    }
  })

  return waitForBackend(BACKEND_READINESS_TIMEOUT_MS)
}

function spawnBackendWithRetry(backend, env) {
  return new Promise((resolve, reject) => {
    let attempts = 0
    let settled = false

    const finish = (callback, value) => {
      if (settled) return
      settled = true
      callback(value)
    }

    const launch = () => {
      if (quitting) {
        finish(resolve, null)
        return
      }

      attempts += 1
      let child
      try {
        child = spawn(backend.command, backend.args, {
          cwd: backend.cwd,
          env,
          // Packaged apps launched from Finder do not have a useful terminal
          // to inherit.  The backend writes its own log file, and ignoring
          // these descriptors avoids an unnecessary resource dependency.
          stdio: isDev ? 'inherit' : 'ignore',
          windowsHide: true
        })
      } catch (error) {
        handleSpawnError(error)
        return
      }

      child.once('spawn', () => finish(resolve, child))
      child.once('error', handleSpawnError)
    }

    const handleSpawnError = (error) => {
      if (settled) return

      const canRetry = !quitting &&
        RETRYABLE_SPAWN_CODES.has(error?.code) &&
        attempts < BACKEND_SPAWN_MAX_ATTEMPTS

      if (!canRetry) {
        finish(reject, error)
        return
      }

      const delay = Math.min(
        2000,
        BACKEND_SPAWN_INITIAL_DELAY_MS * (2 ** (attempts - 1))
      )
      log('backend spawn temporarily unavailable; retrying', {
        code: error.code,
        attempt: attempts,
        nextAttemptInMs: delay
      })
      setTimeout(launch, delay)
    }

    launch()
  })
}

function waitForBackend(timeoutMs = 15000) {
  const startedAt = Date.now()

  return new Promise((resolve) => {
    const probe = () => {
      if (!backendProcess) {
        resolve(false)
        return
      }

      const request = http.get(
        { host: BACKEND_HOST, port: backendPort, path: '/api/config/ip', timeout: 700 },
        (response) => {
          let body = ''
          response.setEncoding('utf8')
          response.on('data', (chunk) => { body += chunk })
          response.on('end', () => {
            const isRadarBackend = response.statusCode === 200 && body.includes('current_ip')
            if (isRadarBackend) {
              log('backend is ready', { statusCode: response.statusCode })
              resolve(true)
            } else {
              retry()
            }
          })
        }
      )
      request.on('error', retry)
      request.on('timeout', () => request.destroy())
    }

    const retry = () => {
      if (Date.now() - startedAt >= timeoutMs) {
        log('backend readiness timeout')
        resolve(false)
        return
      }
      setTimeout(probe, 250)
    }

    probe()
  })
}

function stopBackend() {
  quitting = true
  if (backendProcess && !backendProcess.killed) {
    log('stopping backend')
    backendProcess.kill()
    backendProcess = null
  }
}

function createMainWindow() {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 640,
    autoHideMenuBar: true,
    backgroundColor: '#02103a',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  // Forward renderer console messages to the main process terminal.
  mainWindow.webContents.on('console-message', (_event, level, message, line, sourceId) => {
    const levelName = ['debug', 'info', 'warn', 'error'][level] || 'log'
    console.log(`[renderer:${levelName}] ${sourceId}:${line} ${message}`)
  })

  mainWindow.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL) => {
    log('did-fail-load', { errorCode, errorDescription, validatedURL })
  })

  mainWindow.webContents.on('render-process-gone', (_event, details) => {
    log('render-process-gone', details)
  })

  if (isDev) {
    log('loading dev server', process.env.VITE_DEV_SERVER_URL)
    mainWindow.loadURL(process.env.VITE_DEV_SERVER_URL)
    mainWindow.webContents.openDevTools()
  } else {
    const indexPath = resolveDistIndex()
    log('loading production build', indexPath, 'exists=', fs.existsSync(indexPath))
    if (!fs.existsSync(indexPath)) {
      dialog.showErrorBox(
        '启动失败',
        `未找到构建产物：${indexPath}\n请先运行 npm run build 再启动应用。`
      )
      app.quit()
      return
    }
    mainWindow.loadFile(indexPath)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    if (isDev) {
      mainWindow.webContents.openDevTools()
    }
  })
}

app.whenReady().then(() => {
  log('app ready', { resourcesPath: process.resourcesPath, appPath: app.getAppPath() })
  startBackend().finally(() => createMainWindow())

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('before-quit', stopBackend)
process.on('exit', stopBackend)
