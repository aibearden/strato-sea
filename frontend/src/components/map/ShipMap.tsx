import { useEffect, useRef } from 'react'
import {
  Map as MapLibreMap,
  NavigationControl,
  setWorkerUrl,
  type GeoJSONSource,
  type MapGeoJSONFeature,
  type MapMouseEvent,
} from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url'
import { useDebouncedCallback } from '../../hooks/useDebouncedCallback'
import type { Vessel, Viewport } from '../../types/vessel'
import { createShipIcon, getBaseMap } from './shipIcon'

setWorkerUrl(workerUrl)

const SOURCE_ID = 'vessels'
const SELECTED_SOURCE_ID = 'selected-vessel'
const CLUSTER_LAYER = 'vessel-clusters'
const CLUSTER_COUNT_LAYER = 'vessel-cluster-count'
const SHIP_LAYER = 'vessel-ships'

type VesselFeatureCollection = {
  type: 'FeatureCollection'
  features: Array<{
    type: 'Feature'
    id: number
    geometry: { type: 'Point'; coordinates: [number, number] }
    properties: {
      mmsi: number
      name: string
      heading: number
    }
  }>
}

function toCollection(vessels: Iterable<Vessel>): VesselFeatureCollection {
  const features: VesselFeatureCollection['features'] = []
  for (const vessel of vessels) {
    if (vessel.lat == null || vessel.lon == null) {
      continue
    }
    features.push({
      type: 'Feature',
      id: vessel.mmsi,
      geometry: {
        type: 'Point',
        coordinates: [vessel.lon, vessel.lat],
      },
      properties: {
        mmsi: vessel.mmsi,
        name: vessel.name ?? String(vessel.mmsi),
        heading: vessel.heading ?? vessel.course ?? 0,
      },
    })
  }
  return { type: 'FeatureCollection', features }
}

function selectedCollection(vessel: Vessel | null): VesselFeatureCollection {
  return toCollection(vessel ? [vessel] : [])
}

function readViewport(map: MapLibreMap): Viewport {
  const bounds = map.getBounds()
  return {
    west: bounds.getWest(),
    south: bounds.getSouth(),
    east: bounds.getEast(),
    north: bounds.getNorth(),
    zoom: map.getZoom(),
  }
}

interface ShipMapProps {
  vessels: Map<number, Vessel>
  selectedVessel: Vessel | null
  onViewportChange: (viewport: Viewport) => void
  onSelectVessel: (mmsi: number) => void
  focusToken: number
}

export function ShipMap({
  vessels,
  selectedVessel,
  onViewportChange,
  onSelectVessel,
  focusToken,
}: ShipMapProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const onViewportChangeRef = useRef(onViewportChange)
  const onSelectVesselRef = useRef(onSelectVessel)
  const vesselsRef = useRef(vessels)

  onViewportChangeRef.current = onViewportChange
  onSelectVesselRef.current = onSelectVessel
  vesselsRef.current = vessels

  const emitViewport = useDebouncedCallback((viewport: Viewport) => {
    onViewportChangeRef.current(viewport)
  }, 450)

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return
    }

    const baseMap = getBaseMap()
    const map = new MapLibreMap({
      container: containerRef.current,
      style: baseMap.style,
      center: [103.85, 1.26],
      zoom: 9,
      minZoom: 1.5,
      maxZoom: 18,
      fadeDuration: 0,
      attributionControl: { compact: true },
    })
    map.addControl(new NavigationControl({ showCompass: true }), 'bottom-right')
    mapRef.current = map

    const handleMove = () => {
      emitViewport(readViewport(map))
    }

    map.on('load', () => {
      map.addImage('ship-marker', createShipIcon('#5eead4'), { pixelRatio: 2 })
      map.addImage('ship-marker-selected', createShipIcon('#f8fafc', true), { pixelRatio: 2 })

      map.addSource(SOURCE_ID, {
        type: 'geojson',
        data: toCollection(vesselsRef.current.values()),
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 46,
        promoteId: 'mmsi',
      })

      map.addSource(SELECTED_SOURCE_ID, {
        type: 'geojson',
        data: selectedCollection(null),
      })

      map.addLayer({
        id: CLUSTER_LAYER,
        type: 'circle',
        source: SOURCE_ID,
        filter: ['has', 'point_count'],
        paint: {
          'circle-color': [
            'step',
            ['get', 'point_count'],
            '#134e4a',
            25,
            '#0f766e',
            80,
            '#14b8a6',
          ],
          'circle-radius': ['step', ['get', 'point_count'], 16, 25, 22, 80, 28],
          'circle-stroke-width': 1.5,
          'circle-stroke-color': '#99f6e4',
          'circle-opacity': 0.92,
        },
      })

      map.addLayer({
        id: CLUSTER_COUNT_LAYER,
        type: 'symbol',
        source: SOURCE_ID,
        filter: ['has', 'point_count'],
        layout: {
          'text-field': '{point_count_abbreviated}',
          'text-font': baseMap.clusterFont,
          'text-size': 12,
        },
        paint: {
          'text-color': '#ecfeff',
        },
      })

      map.addLayer({
        id: SHIP_LAYER,
        type: 'symbol',
        source: SOURCE_ID,
        filter: ['!', ['has', 'point_count']],
        layout: {
          'icon-image': 'ship-marker',
          'icon-size': 0.72,
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })

      map.addLayer({
        id: 'selected-halo',
        type: 'circle',
        source: SELECTED_SOURCE_ID,
        paint: {
          'circle-radius': 18,
          'circle-color': '#5eead4',
          'circle-opacity': 0.16,
          'circle-stroke-width': 2,
          'circle-stroke-color': '#99f6e4',
        },
      })

      map.addLayer({
        id: 'selected-ship',
        type: 'symbol',
        source: SELECTED_SOURCE_ID,
        layout: {
          'icon-image': 'ship-marker-selected',
          'icon-size': 0.9,
          'icon-rotate': ['get', 'heading'],
          'icon-rotation-alignment': 'map',
          'icon-allow-overlap': true,
          'icon-ignore-placement': true,
        },
      })

      onViewportChangeRef.current(readViewport(map))
    })

    map.on('moveend', handleMove)
    map.on('zoomend', handleMove)

    map.on('click', CLUSTER_LAYER, async (event: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(event.point, { layers: [CLUSTER_LAYER] })
      const cluster = features[0]
      if (!cluster || cluster.properties?.cluster_id == null) {
        return
      }
      const source = map.getSource(SOURCE_ID) as GeoJSONSource
      const zoom = await source.getClusterExpansionZoom(cluster.properties.cluster_id as number)
      const coordinates = (cluster.geometry as { coordinates: [number, number] }).coordinates
      map.easeTo({ center: coordinates, zoom })
    })

    map.on('click', SHIP_LAYER, (event: MapMouseEvent) => {
      const features = map.queryRenderedFeatures(event.point, { layers: [SHIP_LAYER] })
      const feature = features[0] as MapGeoJSONFeature | undefined
      const rawMmsi = feature?.properties?.mmsi
      const mmsi = typeof rawMmsi === 'number' ? rawMmsi : Number(rawMmsi)
      if (Number.isFinite(mmsi)) {
        onSelectVesselRef.current(mmsi)
      }
    })

    map.on('mouseenter', CLUSTER_LAYER, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', CLUSTER_LAYER, () => {
      map.getCanvas().style.cursor = ''
    })
    map.on('mouseenter', SHIP_LAYER, () => {
      map.getCanvas().style.cursor = 'pointer'
    })
    map.on('mouseleave', SHIP_LAYER, () => {
      map.getCanvas().style.cursor = ''
    })

    return () => {
      map.remove()
      mapRef.current = null
    }
  }, [emitViewport])

  useEffect(() => {
    const map = mapRef.current
    if (!map?.getSource(SOURCE_ID)) {
      return
    }
    const source = map.getSource(SOURCE_ID) as GeoJSONSource
    void source.setData(toCollection(vessels.values()))
    const selectedSource = map.getSource(SELECTED_SOURCE_ID) as GeoJSONSource | undefined
    selectedSource?.setData(selectedCollection(selectedVessel))
  }, [vessels, selectedVessel])

  useEffect(() => {
    if (!focusToken || !selectedVessel || selectedVessel.lat == null || selectedVessel.lon == null) {
      return
    }
    const map = mapRef.current
    if (!map) {
      return
    }
    map.flyTo({
      center: [selectedVessel.lon, selectedVessel.lat],
      zoom: Math.max(map.getZoom(), 10),
      duration: 1100,
      essential: true,
    })
  }, [focusToken, selectedVessel])

  return <div ref={containerRef} className="map-root" />
}
