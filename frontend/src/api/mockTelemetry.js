function formatTimestamp(date = new Date()) {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  const ss = String(date.getSeconds()).padStart(2, '0')
  return `${y}-${m}-${d} ${hh}:${mm}:${ss}`
}

// Legacy compatibility only. Production pages use the authority replay snapshot.
export function buildMockTelemetryPayload() {
  return {
    timestamp: formatTimestamp(),
    system_status: {
      mode: 'AUTO',
      signal_source: 'SAT-A',
      source_status: 'normal',
      lock_status: 'locked',
      lock_indicator: 'green'
    },
    signal_params: {
      agc_threshold: 1.2,
      agc_voltage: 3.5,
      azimuth_error_voltage: 0.02,
      pitch_error_voltage: 0.01
    },
    tracking_data: {
      turntable_system: {
        guide_azimuth: '--',
        guide_pitch: '--',
        guide_tilt: 0,
        current_azimuth: '--',
        current_pitch: '--',
        current_tilt: 0,
        deviation_azimuth: '--', deviation_pitch: '--', deviation_tilt: '--'
      },
      geodetic_system: {
        guide_azimuth: '--', guide_pitch: '--', current_azimuth: '--', current_pitch_alt: '--',
        deviation_azimuth: '--', deviation_pitch: '--'
      }
    },
    motor_diagnostics: {
      motor_1: {
        power_on: true,
        status: 'running',
        current: '--', voltage: '--', inertia: '--', temp: '--'
      },
      motor_2: {
        power_on: true,
        status: 'standby',
        current: '--', voltage: '--', inertia: '--', temp: '--'
      }
    }
  }
}
