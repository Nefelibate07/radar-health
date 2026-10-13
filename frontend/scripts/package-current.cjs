const path = require('path')
const fs = require('fs')
const os = require('os')
const { spawnSync } = require('child_process')

const frontendRoot = path.resolve(__dirname, '..')
const platformNames = {
  darwin: 'mac',
  win32: 'win',
  linux: 'linux'
}
const target = platformNames[process.platform]

if (!target) {
  console.error(`[desktop] unsupported current platform: ${process.platform}`)
  process.exit(2)
}

const builder = path.join(
  frontendRoot,
  'node_modules',
  '.bin',
  process.platform === 'win32' ? 'electron-builder.cmd' : 'electron-builder'
)
// Keep the default current-machine smoke build lightweight.  A release caller
// may explicitly request the installer together with the runnable ZIP.
const requestedMacTargets = process.env.DESKTOP_MAC_TARGETS
  ? process.env.DESKTOP_MAC_TARGETS.split(',').map((item) => item.trim()).filter(Boolean)
  : ['zip']
if (requestedMacTargets.some((item) => !['dmg', 'zip'].includes(item))) {
  console.error('[desktop] DESKTOP_MAC_TARGETS accepts only dmg and zip')
  process.exit(2)
}
const args = target === 'mac'
  ? ['--mac', ...requestedMacTargets, `--${process.arch}`]
  : [`--${target}`, `--${process.arch}`]

args.push('--publish', 'never')

// Allow isolated web/backend build directories so an exploratory package does
// not overwrite a user's existing dist/ or PyInstaller artifacts. The package
// metadata and all unrelated build settings remain the same as package.json.
let temporaryConfigDir = null
const webBuildDir = process.env.DESKTOP_WEB_BUILD_DIR
const backendDistDir = process.env.DESKTOP_BACKEND_DIST_DIR
if (webBuildDir || backendDistDir) {
  const packageMetadata = JSON.parse(fs.readFileSync(path.join(frontendRoot, 'package.json'), 'utf8'))
  const buildConfig = structuredClone(packageMetadata.build || {})
  if (webBuildDir) {
    const files = Array.isArray(buildConfig.files) ? [...buildConfig.files] : []
    const distPatternIndex = files.findIndex((item) => item === 'dist/**/*')
    if (distPatternIndex < 0) {
      throw new Error('[desktop] could not find dist/**/* in package.json build.files')
    }
    // Preserve Electron's expected app.asar/dist/... layout while sourcing
    // files from the isolated build directory. A glob rooted at
    // `dist-openjev/**/*` instead creates app.asar/dist-openjev and makes the
    // packaged main process fail to find dist/index.html.
    files[distPatternIndex] = {
      from: path.relative(frontendRoot, path.resolve(frontendRoot, webBuildDir)).replace(/\\/g, '/'),
      to: 'dist',
      filter: ['**/*']
    }
    buildConfig.files = files
  }
  if (backendDistDir) {
    const resource = (buildConfig.extraResources || []).find((item) => item.to === 'backend-dist')
    if (!resource) {
      throw new Error('[desktop] could not find the backend-dist extraResource in package.json')
    }
    resource.from = path.resolve(frontendRoot, backendDistDir)
  }
  temporaryConfigDir = fs.mkdtempSync(path.join(os.tmpdir(), 'radar-health-electron-config-'))
  const configPath = path.join(temporaryConfigDir, 'electron-builder.json')
  fs.writeFileSync(configPath, JSON.stringify(buildConfig, null, 2))
  args.push('--config', configPath)
}

// Keep prior release folders immutable when the caller requests a named build.
if (process.env.DESKTOP_RELEASE_DIR) {
  args.push(`--config.directories.output=${path.resolve(frontendRoot, process.env.DESKTOP_RELEASE_DIR)}`)
}

if (target === 'win') {
  args.push('--config.win.signAndEditExecutable=false')
}

console.log(`[desktop] packaging ${target}/${process.arch}`)
const result = spawnSync(builder, args, {
  cwd: frontendRoot,
  env: {
    ...process.env,
    ELECTRON_MIRROR: process.env.ELECTRON_MIRROR || 'https://npmmirror.com/mirrors/electron/',
    ELECTRON_BUILDER_BINARIES_MIRROR: process.env.ELECTRON_BUILDER_BINARIES_MIRROR || 'https://npmmirror.com/mirrors/electron-builder-binaries/'
  },
  stdio: 'inherit',
  // Windows command shims (.cmd) cannot be launched by spawnSync without
  // shell mode; Node otherwise reports EINVAL before electron-builder starts.
  shell: process.platform === 'win32'
})

if (temporaryConfigDir) {
  fs.rmSync(temporaryConfigDir, { recursive: true, force: true })
}

if (result.error) {
  console.error(`[desktop] failed to start electron-builder: ${result.error.message}`)
  process.exit(1)
}

process.exit(result.status || 0)
