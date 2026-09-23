import type { StreamStatus } from '../types/vessel'

interface StatusBarProps {
  connected: boolean
  status: StreamStatus
  vesselCount: number
}

export function StatusBar({ connected, status, vesselCount }: StatusBarProps) {
  const aisLabel = status.ais_connected ? 'AIS live' : 'AIS idle'
  const streamLabel = status.subscription_active ? 'Viewport stream' : 'Zoom to stream'
  const hint = status.message ?? (connected ? 'Map connected' : 'Connecting to backend')

  return (
    <div className="status-bar">
      <span className={`status-dot ${status.ais_connected ? 'on' : 'off'}`} />
      <span>{aisLabel}</span>
      <span className="status-sep">·</span>
      <span>{streamLabel}</span>
      <span className="status-sep">·</span>
      <span>{vesselCount} ships</span>
      <span className="status-hint">{hint}</span>
    </div>
  )
}
