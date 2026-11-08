import { useEffect, useRef, useState } from 'react'
import type { LiveState, Topology } from './types'

export async function api<T = unknown>(path: string, body?: unknown, method?: string): Promise<T> {
  const res = await fetch(`/api${path}`, {
    method: method ?? (body === undefined ? 'GET' : 'POST'),
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let detail = res.statusText
    try { detail = (await res.json()).detail ?? detail } catch { /* ignore */ }
    throw new Error(detail)
  }
  return res.json() as Promise<T>
}

/** Live state over WebSocket with automatic reconnect. */
export function useLive() {
  const [state, setState] = useState<LiveState | null>(null)
  const [topology, setTopology] = useState<Topology | null>(null)
  const [connected, setConnected] = useState(false)
  const retry = useRef(0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let timer: number | undefined

    const connect = () => {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws`)
      ws.onopen = () => { setConnected(true); retry.current = 0 }
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data) as LiveState
        if (msg.topology) setTopology(msg.topology)
        setState(msg)
      }
      ws.onclose = () => {
        setConnected(false)
        if (closed) return
        retry.current = Math.min(retry.current + 1, 6)
        timer = window.setTimeout(connect, 400 * retry.current)
      }
      ws.onerror = () => ws?.close()
    }
    connect()
    return () => { closed = true; window.clearTimeout(timer); ws?.close() }
  }, [])

  // Fallback: refetch topology if the version moved and the WS message lacked it
  useEffect(() => {
    if (state && topology && state.topology_version !== topology.version) {
      api<Topology>('/topology').then(setTopology).catch(() => {})
    }
  }, [state, topology])

  return { state, topology, connected }
}

export function fmtEta(min: number | null | undefined): string {
  if (min === null || min === undefined) return '—'
  if (min <= 0) return 'now'
  if (min < 1) return '<1 min'
  if (min < 90) return `~${Math.round(min)} min`
  return `~${(min / 60).toFixed(1)} h`
}

export function fmtCountdown(min: number | null | undefined): string {
  if (min === null || min === undefined) return '—'
  const s = Math.max(0, Math.round(min * 60))
  const m = Math.floor(s / 60)
  return `${m}:${String(s % 60).padStart(2, '0')}`
}

export const hhmm = (iso: string | null | undefined) => (iso ? iso.slice(11, 16) : '—')
export const hhmmss = (iso: string | null | undefined) => (iso ? iso.slice(11, 19) : '—')
