import type { Vessel } from '../types/vessel'

interface VesselPanelProps {
  vessel: Vessel | null
  onClose: () => void
}

function formatCoord(value: number | null, kind: 'lat' | 'lon'): string {
  if (value == null) {
    return '—'
  }
  const hemisphere =
    kind === 'lat' ? (value >= 0 ? 'N' : 'S') : value >= 0 ? 'E' : 'W'
  return `${Math.abs(value).toFixed(5)}° ${hemisphere}`
}

function formatNumber(value: number | null, suffix: string): string {
  if (value == null) {
    return '—'
  }
  return `${value.toFixed(1)} ${suffix}`
}

function formatTime(value: string | null): string {
  if (!value) {
    return '—'
  }
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(undefined, { hour12: false })
}

export function VesselPanel({ vessel, onClose }: VesselPanelProps) {
  if (!vessel) {
    return null
  }

  const rows: Array<[string, string]> = [
    ['Name', vessel.name ?? '—'],
    ['MMSI', String(vessel.mmsi)],
    ['IMO', vessel.imo ? String(vessel.imo) : '—'],
    ['Call sign', vessel.call_sign ?? '—'],
    ['Vessel type', vessel.vessel_type_label ?? (vessel.vessel_type != null ? String(vessel.vessel_type) : '—')],
    ['Latitude', formatCoord(vessel.lat, 'lat')],
    ['Longitude', formatCoord(vessel.lon, 'lon')],
    ['Speed', formatNumber(vessel.speed, 'kn')],
    ['Course', formatNumber(vessel.course, '°')],
    ['Heading', formatNumber(vessel.heading, '°')],
    ['Destination', vessel.destination ?? '—'],
    ['ETA', vessel.eta ?? '—'],
    ['Last update', formatTime(vessel.last_update)],
  ]

  return (
    <aside className="vessel-panel" aria-live="polite">
      <div className="panel-header">
        <div>
          <p className="panel-kicker">Vessel</p>
          <h2>{vessel.name ?? `MMSI ${vessel.mmsi}`}</h2>
        </div>
        <button type="button" className="icon-button" onClick={onClose} aria-label="Close vessel details">
          ×
        </button>
      </div>
      <dl className="panel-grid">
        {rows.map(([label, value]) => (
          <div key={label} className="panel-row">
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </aside>
  )
}
