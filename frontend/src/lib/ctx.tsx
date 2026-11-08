import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'
import { api } from './api'
import type { LiveState, Topology, TopoNode } from './types'

export type Page = 'console' | 'incidents' | 'migrations' | 'handoff' | 'oncall' | 'myview'

interface Toast { id: number; text: string; tone: 'ok' | 'err' | 'info' }

interface Ctx {
  state: LiveState
  topology: Topology
  nodeById: Record<string, TopoNode>
  viewer: string
  setViewer: (id: string) => void
  page: Page
  setPage: (p: Page) => void
  openIncident: string | null
  setOpenIncident: (id: string | null) => void
  selectedNode: string | null
  setSelectedNode: (id: string | null) => void
  act: <T = unknown>(path: string, body?: Record<string, unknown>, okText?: string) => Promise<T | undefined>
  toasts: Toast[]
  toast: (text: string, tone?: Toast['tone']) => void
}

const C = createContext<Ctx | null>(null)

export function useApp() {
  const v = useContext(C)
  if (!v) throw new Error('useApp outside provider')
  return v
}

export function AppProvider({ state, topology, children }: { state: LiveState; topology: Topology; children: ReactNode }) {
  const defaultViewer = state.engineers.find((e) => e.on_shift && e.role === 'lead')?.id ?? state.engineers[0]?.id
  const [viewer, setViewerRaw] = useState<string>(() => {
    try { return localStorage.getItem('ds.viewer') ?? defaultViewer } catch { return defaultViewer }
  })
  const [page, setPage] = useState<Page>('console')
  const [openIncident, setOpenIncident] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])

  const setViewer = useCallback((id: string) => {
    setViewerRaw(id)
    try { localStorage.setItem('ds.viewer', id) } catch { /* private mode */ }
  }, [])

  const toast = useCallback((text: string, tone: Toast['tone'] = 'info') => {
    const id = Date.now() + Math.random()
    setToasts((t) => [...t, { id, text, tone }])
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 3800)
  }, [])

  const act = useCallback(async <T,>(path: string, body: Record<string, unknown> = {}, okText?: string) => {
    try {
      const r = await api<T>(path, { actor: viewer, ...body })
      if (okText) toast(okText, 'ok')
      return r
    } catch (e) {
      toast((e as Error).message, 'err')
      return undefined
    }
  }, [viewer, toast])

  const nodeById = useMemo(() => Object.fromEntries(topology.nodes.map((n) => [n.id, n])), [topology])

  return (
    <C.Provider value={{ state, topology, nodeById, viewer, setViewer, page, setPage, openIncident, setOpenIncident,
      selectedNode, setSelectedNode, act, toasts, toast }}>
      {children}
    </C.Provider>
  )
}
