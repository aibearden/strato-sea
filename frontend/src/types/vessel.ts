export interface Vessel {
  mmsi: number
  name: string | null
  imo: number | null
  call_sign: string | null
  vessel_type: number | null
  vessel_type_label: string | null
  lat: number | null
  lon: number | null
  speed: number | null
  course: number | null
  heading: number | null
  destination: string | null
  eta: string | null
  nav_status: number | null
  last_update: string
}

export interface Viewport {
  west: number
  south: number
  east: number
  north: number
  zoom: number
}

export interface StreamStatus {
  ais_connected: boolean
  subscription_active: boolean
  strategy: string
  vessel_count: number
  tracked_total: number
  message: string | null
}

export interface SnapshotMessage {
  type: 'snapshot'
  vessels: Vessel[]
  strategy: string
  subscription_active: boolean
}

export interface UpdateMessage {
  type: 'update'
  vessels: Vessel[]
}

export interface RemoveMessage {
  type: 'remove'
  mmsis: number[]
}

export interface StatusMessage extends StreamStatus {
  type: 'status'
}

export interface ErrorMessage {
  type: 'error'
  message: string
}

export interface PongMessage {
  type: 'pong'
}

export type ServerMessage =
  | SnapshotMessage
  | UpdateMessage
  | RemoveMessage
  | StatusMessage
  | ErrorMessage
  | PongMessage

export interface SearchResponse {
  vessels: Vessel[]
  query: string
}
