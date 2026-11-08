import { useEffect, useMemo, useState } from 'react'
import { FlaskConical, MousePointerClick, Wrench } from 'lucide-react'
import { useApp } from '../lib/ctx'
import { api, fmtEta } from '../lib/api'
import type { Blast } from '../lib/types'
import TopologyGraph, { type Highlight } from '../components/graph/TopologyGraph'
import { BlastPanel, IncidentQueue, Timeline } from '../components/Panels'
import { PageHeader } from '../components/Shell'
import { Button, STATUS_COLOR, STATUS_LABEL, Stat } from '../components/ui'

export function blastToHighlight(b: Blast | null | undefined, mode?: Highlight['mode']): Highlight | null {
  if (!b || !b.sources?.length) return null
  const affected: Highlight['affected'] = {}
  for (const a of b.affected) affected[a.id] = { status: a.status !== 'ok' ? a.status : 'at_risk', eta: a.eta }
  return { sources: b.sources, affected, mode: mode ?? b.mode }
}

export function useNodeBlast(nodeId: string | null) {
  const [blast, setBlast] = useState<Blast | null>(null)
  useEffect(() => {
    setBlast(null)
    if (!nodeId) return
    let alive = true
    const load = () => api<Blast>(`/blast/${nodeId}`).then((b) => alive && setBlast(b)).catch(() => {})
    load()
    const t = window.setInterval(load, 2000)
    return () => { alive = false; window.clearInterval(t) }
  }, [nodeId])
  return blast
}

export default function ConsolePage() {
  const { state, topology, selectedNode, setSelectedNode, act } = useApp()
  const [region, setRegion] = useState<string | null>(topology.regions[0]?.id ?? null)
  const [focused, setFocused] = useState<string | null>(null)
  const [whatIf, setWhatIf] = useState(false)
  const [whatIfSel, setWhatIfSel] = useState<string[]>([])
  const [whatIfBlast, setWhatIfBlast] = useState<Blast | null>(null)
  const nodeBlast = useNodeBlast(whatIf ? null : selectedNode)

  useEffect(() => {
    if (!whatIf || !whatIfSel.length) { setWhatIfBlast(null); return }
    let alive = true
    const load = () => api<Blast>('/whatif', { nodes: whatIfSel }).then((b) => alive && setWhatIfBlast(b)).catch(() => {})
    load()
    const t = window.setInterval(load, 2500)
    return () => { alive = false; window.clearInterval(t) }
  }, [whatIf, whatIfSel])

  const focusedInc = state.incidents.find((i) => i.id === focused)
  const activeBlast = whatIf ? whatIfBlast : selectedNode ? nodeBlast : focusedInc?.blast ?? null
  const highlight = useMemo(() => blastToHighlight(activeBlast, whatIf ? 'whatif' : undefined), [activeBlast, whatIf])

  const onNodeClick = (id: string) => {
    if (whatIf) setWhatIfSel((s) => (s.includes(id) ? s.filter((x) => x !== id) : [...s, id]))
    else { setFocused(null); setSelectedNode(selectedNode === id ? null : id) }
  }

  // KPIs
  const open = state.incidents.filter((i) => i.status !== 'resolved' && !i.title.startsWith('[merged'))
  const p1 = open.filter((i) => i.priority === 'P1').length
  const unacked = open.filter((i) => i.status === 'open').length
  const workloads = topology.nodes.filter((n) => n.kind === 'workload')
  const impacted = workloads.filter((w) => state.nodes[w.id]?.status !== 'ok' || state.nodes[w.id]?.forecast).length
  const exposure = useMemo(() => {
    const seen = new Map<string, number>()
    open.forEach((i) => i.blast.customers?.forEach((c) => seen.set(c.name, c.penalty_per_hour)))
    return [...seen.values()].reduce((a, b) => a + b, 0)
  }, [open])
  const maint = state.faults.filter((f) => f.preset === 'maintenance')

  return (
    <div className="flex h-full min-h-0 flex-col overflow-y-auto">
      <PageHeader crumbs={['datasurge', 'Operations', 'Console']} title="Your infrastructure. At a glance."
        actions={<span className="text-[11.5px] text-muted">{topology.nodes.length} components · {topology.regions.length} regions · {workloads.length} AI workloads</span>}>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          <Stat label="Open incidents" value={open.length} sub={`${p1} P1 · ${unacked} unacknowledged`} color={p1 ? '#f43f5e' : '#dce7fb'} />
          <Stat label="Workloads impacted" value={`${impacted}/${workloads.length}`} sub="degraded, down or forecast" color={impacted ? '#fb923c' : '#34d399'} />
          <Stat label="SLA exposure" value={`$${(exposure / 1000).toFixed(0)}k/hr`} sub="customers in blast radius" color={exposure ? '#f43f5e' : '#dce7fb'} />
          <Stat label="Next handoff" value={fmtEta(state.clock.shift.next_change_in_min).replace('~', '')} sub={`${state.clock.shift.name} → next`} />
        </div>
      </PageHeader>

      <div className="console-workspace flex min-h-0 flex-1 gap-5 p-6">
        <div className="flex min-w-0 flex-1 flex-col gap-3">
          <section className="relative flex min-h-[520px] flex-1 flex-col overflow-hidden rounded-lg border border-line bg-ink-900">
            <div className="flex flex-wrap items-center gap-2 border-b border-line bg-ink-850 px-5 py-3">
              <h3 className="text-[13px] font-semibold">Infrastructure map</h3>
              <div className="ml-2 flex overflow-hidden rounded-md border border-line-strong">
                {[null, ...topology.regions.map((r) => r.id)].map((r) => (
                  <button key={r ?? 'all'} onClick={() => setRegion(r)}
                    className={`px-2.5 py-1 text-[11.5px] ${region === r ? 'bg-brand text-white' : 'text-sky hover:bg-ink-700'}`}>{r ?? 'All regions'}</button>
                ))}
              </div>
              <Button size="sm" variant={whatIf ? 'primary' : 'secondary'}
                onClick={() => { setWhatIf(!whatIf); setWhatIfSel([]); setSelectedNode(null); setFocused(null) }}>
                <FlaskConical size={13} /> {whatIf ? 'Exit what-if' : 'What-if mode'}
              </Button>
              <span className="hidden items-center gap-1 text-[11px] text-faint lg:flex">
                <MousePointerClick size={12} /> {whatIf ? 'Click components to plan maintenance' : 'Click a component to see its blast radius'}
              </span>
              <div className="ml-auto flex items-center gap-3">
                {(['ok', 'at_risk', 'degraded', 'down', 'maintenance'] as const).map((s) => (
                  <span key={s} className="flex items-center gap-1 text-[11px] text-muted">
                    <span className="size-2 rounded-sm" style={{ background: STATUS_COLOR[s] }} />{STATUS_LABEL[s]}
                  </span>
                ))}
              </div>
            </div>
            {maint.length > 0 && (
              <div className="flex items-center gap-2 border-b border-maint/40 bg-maint/10 px-5 py-3 text-[12px] text-[#ddd6fe]">
                <Wrench size={13} /> Maintenance in progress: {maint.map((f) => topology.nodes.find((n) => n.id === f.target)?.name).join(', ')}
                <Button size="sm" className="ml-auto" onClick={() => act('/maintenance/end', {}, 'Maintenance ended')}>End maintenance</Button>
              </div>
            )}
            <div className="relative min-h-0 flex-1">
              <TopologyGraph topology={topology} nodes={state.nodes} highlight={highlight}
                selected={whatIf ? whatIfSel : selectedNode ? [selectedNode] : []}
                onNodeClick={onNodeClick} onPaneClick={() => { if (!whatIf) { setSelectedNode(null); setFocused(null) } }}
                regionFilter={selectedNode ? topology.nodes.find(n => n.id === selectedNode)?.region : region} />
              {(whatIf || selectedNode || focusedInc) && (
                <div className="absolute bottom-3 left-3 top-3 z-20 flex flex-col">
                  <BlastPanel
                    blast={activeBlast} nodeId={whatIf ? null : selectedNode ?? (focusedInc?.root ?? null)}
                    onClose={() => { setSelectedNode(null); setFocused(null); setWhatIf(false); setWhatIfSel([]) }}
                    whatIf={whatIf ? whatIfSel : undefined}
                    onCancelWhatIf={() => { setWhatIf(false); setWhatIfSel([]) }}
                    onStartMaintenance={async () => {
                      await act('/maintenance/start', { nodes: whatIfSel }, 'Maintenance started — migrations will be suggested')
                      setWhatIf(false); setWhatIfSel([])
                    }} />
                </div>
              )}
            </div>
          </section>
          <details className="rounded-lg border border-line bg-ink-900"><summary className="cursor-pointer px-5 py-4 text-muted">Recent activity · alerts, actions &amp; handoffs</summary><Timeline className="h-[250px]" /></details>
        </div>
        <div className="incident-column w-[300px] shrink-0">
          <IncidentQueue focused={focused} onFocus={(id) => { setFocused(id); setSelectedNode(null); setWhatIf(false) }} />
        </div>
      </div>
    </div>
  )
}
