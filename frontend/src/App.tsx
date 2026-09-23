import { useMemo, useState } from 'react'
import { SearchBar } from './components/SearchBar'
import { StatusBar } from './components/StatusBar'
import { VesselPanel } from './components/VesselPanel'
import { ShipMap } from './components/map/ShipMap'
import { useAisStream } from './hooks/useAisStream'
import type { Vessel } from './types/vessel'

function App() {
  const { vessels, status, connected, updateViewport } = useAisStream()
  const [selected, setSelected] = useState<Vessel | null>(null)
  const [focusToken, setFocusToken] = useState(0)

  const selectedVessel = useMemo(() => {
    if (!selected) {
      return null
    }
    return vessels.get(selected.mmsi) ?? selected
  }, [selected, vessels])

  const selectVessel = (vessel: Vessel) => {
    setSelected(vessel)
    setFocusToken((value) => value + 1)
  }

  return (
    <div className="app-shell">
      <ShipMap
        vessels={vessels}
        selectedVessel={selectedVessel}
        onViewportChange={updateViewport}
        onSelectVessel={(mmsi) => {
          const vessel = vessels.get(mmsi)
          if (vessel) {
            selectVessel(vessel)
          }
        }}
        focusToken={focusToken}
      />
      <header className="top-chrome">
        <div className="brand">
          <span className="brand-mark" />
          <div>
            <strong>Strato Sea</strong>
            <p>Live AIS · viewport stream</p>
          </div>
        </div>
        <SearchBar onSelect={selectVessel} />
      </header>
      <VesselPanel vessel={selectedVessel} onClose={() => setSelected(null)} />
      <StatusBar connected={connected} status={status} vesselCount={vessels.size} />
    </div>
  )
}

export default App
