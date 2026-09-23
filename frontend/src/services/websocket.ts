import type { ServerMessage, Viewport } from '../types/vessel'

const WS_PATH = '/ws/ais'

export function createAisSocket(): WebSocket {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${window.location.host}${WS_PATH}`)
}

export function sendViewport(socket: WebSocket, viewport: Viewport): void {
  if (socket.readyState !== WebSocket.OPEN) {
    return
  }
  socket.send(
    JSON.stringify({
      type: 'viewport',
      ...viewport,
    }),
  )
}

export function parseServerMessage(raw: string): ServerMessage | null {
  try {
    const parsed = JSON.parse(raw) as ServerMessage
    if (!parsed || typeof parsed !== 'object' || !('type' in parsed)) {
      return null
    }
    return parsed
  } catch {
    return null
  }
}
