import { useEffect, useRef, useState } from 'react'
import { searchVessels } from '../services/api'
import { useDebouncedCallback } from '../hooks/useDebouncedCallback'
import type { Vessel } from '../types/vessel'

interface SearchBarProps {
  onSelect: (vessel: Vessel) => void
}

export function SearchBar({ onSelect }: SearchBarProps) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Vessel[]>([])
  const [open, setOpen] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const boxRef = useRef<HTMLDivElement | null>(null)

  const runSearch = useDebouncedCallback(async (value: string) => {
    if (!value.trim()) {
      setResults([])
      setError(null)
      return
    }
    try {
      const vessels = await searchVessels(value)
      setResults(vessels)
      setError(null)
      setOpen(true)
    } catch {
      setError('Search unavailable')
    }
  }, 250)

  useEffect(() => {
    const onPointerDown = (event: PointerEvent) => {
      if (!boxRef.current?.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    window.addEventListener('pointerdown', onPointerDown)
    return () => window.removeEventListener('pointerdown', onPointerDown)
  }, [])

  return (
    <div className="search-wrap" ref={boxRef}>
      <label className="search-label" htmlFor="vessel-search">
        Search vessels
      </label>
      <input
        id="vessel-search"
        className="search-input"
        value={query}
        placeholder="Search name, MMSI, IMO, or call sign"
        onChange={(event) => {
          const value = event.target.value
          setQuery(value)
          runSearch(value)
        }}
        onFocus={() => {
          if (results.length) {
            setOpen(true)
          }
        }}
        autoComplete="off"
      />
      {open && (results.length > 0 || error || query.trim()) && (
        <ul className="search-results" role="listbox">
          {error && <li className="search-empty">{error}</li>}
          {!error && results.length === 0 && (
            <li className="search-empty">No matching vessels in recent AIS data</li>
          )}
          {results.map((vessel) => (
            <li key={vessel.mmsi}>
              <button
                type="button"
                className="search-result"
                onClick={() => {
                  onSelect(vessel)
                  setQuery(vessel.name ?? String(vessel.mmsi))
                  setOpen(false)
                }}
              >
                <span className="search-result-name">{vessel.name ?? 'Unknown vessel'}</span>
                <span className="search-result-meta">
                  MMSI {vessel.mmsi}
                  {vessel.call_sign ? ` · ${vessel.call_sign}` : ''}
                  {vessel.imo ? ` · IMO ${vessel.imo}` : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
