import { useCallback, useEffect, useRef, useState } from 'react'
import { createAisSocket, parseServerMessage, sendViewport } from '../services/websocket'
import type { StreamStatus, Vessel, Viewport } from '../types/vessel'

const INITIAL_STATUS: StreamStatus = {
  ais_connected: false,
  subscription_active: false,
  strategy: 'defer',
  vessel_count: 0,
  tracked_total: 0,
  message: 'Connecting…',
}

export function useAisStream() {
  const socketRef = useRef<WebSocket | null>(null)
  const vesselsRef = useRef<Map<number, Vessel>>(new Map())
  const [vessels, setVessels] = useState<Map<number, Vessel>>(new Map())
  const [status, setStatus] = useState<StreamStatus>(INITIAL_STATUS)
  const [connected, setConnected] = useState(false)

  const publishVessels = useCallback((next: Map<number, Vessel>) => {
    vesselsRef.current = next
    setVessels(next)
  }, [])

  useEffect(() => {
    let cancelled = false
    let pingTimer: number | undefined
    let reconnectTimer: number | undefined
    let attempt = 0

    const connect = () => {
      if (cancelled) {
        return
      }
      const socket = createAisSocket()
      socketRef.current = socket

      socket.onopen = () => {
        if (cancelled) {
          return
        }
        attempt = 0
        setConnected(true)
        pingTimer = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: 'ping' }))
          }
        }, 25000)
      }

      socket.onmessage = (event: MessageEvent<string>) => {
        const message = parseServerMessage(event.data)
        if (!message) {
          return
        }
        if (message.type === 'snapshot') {
          const next = new Map<number, Vessel>()
          for (const vessel of message.vessels) {
            next.set(vessel.mmsi, vessel)
          }
          publishVessels(next)
          setStatus((prev) => ({
            ...prev,
            strategy: message.strategy,
            subscription_active: message.subscription_active,
            vessel_count: next.size,
          }))
          return
        }
        if (message.type === 'update') {
          const next = new Map(vesselsRef.current)
          for (const vessel of message.vessels) {
            next.set(vessel.mmsi, vessel)
          }
          publishVessels(next)
          return
        }
        if (message.type === 'remove') {
          const next = new Map(vesselsRef.current)
          for (const mmsi of message.mmsis) {
            next.delete(mmsi)
          }
          publishVessels(next)
          return
        }
        if (message.type === 'status') {
          setStatus({
            ais_connected: message.ais_connected,
            subscription_active: message.subscription_active,
            strategy: message.strategy,
            vessel_count: vesselsRef.current.size,
            tracked_total: message.tracked_total,
            message: message.message,
          })
        }
      }

      socket.onclose = () => {
        setConnected(false)
        if (pingTimer !== undefined) {
          window.clearInterval(pingTimer)
        }
        if (cancelled) {
          return
        }
        const delay = Math.min(1000 * 2 ** attempt, 15000)
        attempt += 1
        reconnectTimer = window.setTimeout(connect, delay)
      }
    }

    connect()

    return () => {
      cancelled = true
      if (pingTimer !== undefined) {
        window.clearInterval(pingTimer)
      }
      if (reconnectTimer !== undefined) {
        window.clearTimeout(reconnectTimer)
      }
      socketRef.current?.close()
      socketRef.current = null
    }
  }, [publishVessels])

  const updateViewport = useCallback((viewport: Viewport) => {
    const socket = socketRef.current
    if (socket) {
      sendViewport(socket, viewport)
    }
  }, [])

  return { vessels, status, connected, updateViewport }
}
