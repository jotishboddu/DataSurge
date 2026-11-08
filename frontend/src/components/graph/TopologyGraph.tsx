import { memo, useEffect, useMemo } from 'react'
import {
  Background, BackgroundVariant, Controls, Handle, MiniMap, Position, ReactFlow, ReactFlowProvider, useReactFlow,
  type Edge, type Node, type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Clock, Star } from 'lucide-react'
import type { NodeState, Status, Topology, TopoNode } from '../../lib/types'
import { KindIcon, REGION_COLOR, STATUS_COLOR, STATUS_LABEL } from '../ui'
import { COLUMNS, NODE_H, NODE_W, layoutTopology } from './layout'

export interface Highlight {
  sources: string[]
  affected: Record<string, { status: Status; eta: number | null }>
  mode: 'live' | 'hypothetical' | 'whatif'
}

interface Props {
  topology: Topology
  nodes: Record<string, NodeState>
  highlight: Highlight | null
  selected: string[]
  onNodeClick: (id: string) => void
  onPaneClick?: () => void
  regionFilter?: string | null
  focusIds?: Set<string> | null
  compact?: boolean
}

type CompData = {
  node: TopoNode
  st?: NodeState
  impact: Status | 'source' | null
  eta: number | null
  dim: boolean
  selected: boolean
}

type RegionData = { name: string; region: string; width: number; height: number; colX: number[]; counts: Record<string, number> }

const n1 = (v: unknown, d = 0) => (typeof v === 'number' ? v.toFixed(d) : '—')

function subline(n: TopoNode, st?: NodeState): string {
  const m = st?.metrics ?? {}
  switch (n.kind) {
    case 'power_feed': return `${n1(m.voltage_v)} V · ${n1(m.load_kw)} kW`
    case 'ups': return m.on_battery ? `On battery · ${n1(m.battery_pct)}%` : `Online · ${n1(m.load_pct)}% load`
    case 'chiller': return `Supply ${n1(m.supply_c, 1)}°C`
    case 'crac': return `Air ${n1(m.supply_air_c, 1)}°C · fan ${n1(m.fan_pct)}%`
    case 'spine':
    case 'leaf': return `loss ${n1(m.loss_pct, 2)}% · util ${n1(m.util_pct)}%`
    case 'rack': return `Inlet ${n1(m.inlet_c, 1)}°C · ${n1(m.power_kw)} kW`
    case 'gpu_node': return `${n.gpus_used ?? 0}/${n.gpus_total} used · ${n1(m.temp_c)}°C`
    case 'storage': return `${n1(m.latency_ms, 1)} ms · ${m.failed_disks ?? 0} OSD down`
    case 'workload':
      if (n.wtype === 'inference') return `p99 ${n1(m.p99_ms)} ms · ${n1(m.qps)} qps`
      return `${m.state ?? 'running'} · ${n1(m.throughput_pct)}% tput`
  }
}

const ComponentNode = memo(function ComponentNode({ data }: NodeProps<Node<CompData>>) {
  const { node, st, impact, eta, dim, selected } = data
  const status = st?.maintenance ? 'maintenance' : (st?.status ?? 'ok')
  const ring = impact === 'source' ? '#4c8df6' : impact ? STATUS_COLOR[impact] : status !== 'ok' ? STATUS_COLOR[status] : null
  const regionC = REGION_COLOR[node.region] ?? '#4c8df6'
  const fc = st?.forecast
  return (
    <div
      className={`group relative flex items-center gap-2 overflow-hidden rounded-md border bg-ink-800 pl-2.5 pr-2 transition-[opacity,box-shadow] duration-200 ${impact === 'source' ? 'pulse-ring' : ''}`}
      style={{
        width: NODE_W, height: NODE_H, opacity: dim ? 0.28 : 1,
        borderColor: ring ?? '#22406a',
        boxShadow: selected ? '0 0 0 2px #4c8df6' : ring ? `0 0 0 1px ${ring}66, 0 0 14px ${ring}33` : 'none',
      }}
      title={`${node.name}\n${STATUS_LABEL[status]}${st?.reason ? ' — ' + st.reason : ''}${fc ? `\nForecast: ${fc.status} in ~${Math.round(fc.eta)} min (${fc.reason})` : ''}`}
    >
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: STATUS_COLOR[status] }} />
      <span className="grid size-7 shrink-0 place-items-center rounded" style={{ background: `${regionC}1c`, color: regionC }}>
        <KindIcon kind={node.kind} wtype={node.wtype} size={15} />
      </span>
      <div className="min-w-0 flex-1 leading-tight">
        <div className="flex items-center gap-1 truncate text-[14px] font-medium text-text">
          {node.kind === 'workload' && node.tier === 'platinum' && <Star size={10} className="shrink-0 fill-sky text-sky" />}
          <span className="truncate">{node.name}</span>
        </div>
        <div className="truncate font-mono text-[12px] text-muted">{subline(node, st)}</div>
      </div>
      {(eta !== null && eta > 0) || (fc && !impact) ? (
        <span className="absolute right-1 top-1 inline-flex items-center gap-0.5 rounded bg-ink-950/80 px-1 font-mono text-[9.5px] font-semibold"
          style={{ color: STATUS_COLOR[(fc?.status ?? 'degraded')] }}>
          <Clock size={9} />{Math.round(eta ?? fc?.eta ?? 0)}m
        </span>
      ) : null}
      <Handle type="target" position={Position.Left} isConnectable={false} />
      <Handle type="source" position={Position.Right} isConnectable={false} />
    </div>
  )
})

const RegionNode = memo(function RegionNode({ data }: NodeProps<Node<RegionData>>) {
  const c = REGION_COLOR[data.region] ?? '#4c8df6'
  return (
    <div className="pointer-events-none relative rounded-xl border"
      style={{ width: data.width, height: data.height, borderColor: `${c}40`, background: `linear-gradient(180deg, ${c}10, ${c}04 60px, transparent)` }}>
      <div className="flex items-center gap-2 px-4 pt-2.5">
        <span className="size-2 rounded-full" style={{ background: c }} />
        <span className="text-[13px] font-semibold text-text">{data.region}</span>
        <span className="text-[11.5px] text-muted">{data.name}</span>
        <span className="ml-3 flex items-center gap-2 text-[11px]">
          {(['down', 'degraded', 'at_risk'] as const).map((s) => data.counts[s] ? (
            <span key={s} className="inline-flex items-center gap-1" style={{ color: STATUS_COLOR[s] }}>
              <span className="size-1.5 rounded-full" style={{ background: STATUS_COLOR[s] }} />{data.counts[s]} {STATUS_LABEL[s].toLowerCase()}
            </span>) : null)}
          {!data.counts.down && !data.counts.degraded && !data.counts.at_risk && <span className="text-ok">all healthy</span>}
        </span>
      </div>
      {COLUMNS.map((col, i) => (
        <div key={col.label} className="absolute top-[32px] text-[9.5px] font-semibold uppercase tracking-[0.12em] text-faint"
          style={{ left: data.colX[i], width: NODE_W }}>{col.label}</div>
      ))}
    </div>
  )
})

const nodeTypes = { comp: ComponentNode, region: RegionNode }

function Inner(props: Props) {
  const { topology, nodes: live, highlight, selected, onNodeClick, onPaneClick, regionFilter, focusIds, compact } = props
  const rf = useReactFlow()

  const include = useMemo(() => {
    if (focusIds) return focusIds
    if (regionFilter) return new Set(topology.nodes.filter((n) => n.region === regionFilter).map((n) => n.id))
    return undefined
  }, [focusIds, regionFilter, topology])

  const layout = useMemo(() => layoutTopology(topology, include), [topology, include])
  const layoutKey = `${topology.version}-${regionFilter ?? 'all'}-${focusIds ? [...focusIds].sort().join(',') : ''}`

  const rfNodes = useMemo<Node[]>(() => {
    const byId = Object.fromEntries(topology.nodes.map((n) => [n.id, n]))
    const out: Node[] = []
    for (const b of layout.bands) {
      const counts: Record<string, number> = {}
      for (const p of layout.placed) {
        if (p.region !== b.region) continue
        const s = live[p.id]?.status
        if (s) counts[s] = (counts[s] ?? 0) + 1
      }
      out.push({
        id: `region:${b.region}`, type: 'region', position: { x: 0, y: b.y }, draggable: false, selectable: false,
        data: { name: b.name, region: b.region, width: b.width, height: b.height, colX: layout.colX, counts },
        style: { width: b.width, height: b.height }, zIndex: -1,
      })
    }
    const hl = highlight
    const hlSet = hl ? new Set([...hl.sources, ...Object.keys(hl.affected)]) : null
    for (const p of layout.placed) {
      const n = byId[p.id]
      const impact: CompData['impact'] = hl?.sources.includes(p.id) ? 'source' : hl?.affected[p.id]?.status ?? null
      const band = layout.bands.find((b) => b.region === p.region)!
      out.push({
        id: p.id, type: 'comp', position: { x: p.x, y: band.y + p.y }, draggable: false,
        data: {
          node: n, st: live[p.id], impact: impact as CompData['impact'],
          eta: hl?.affected[p.id]?.eta ?? null,
          dim: !!hlSet && !hlSet.has(p.id), selected: selected.includes(p.id),
        },
      })
    }
    return out
  }, [layout, topology, live, highlight, selected])

  const rfEdges = useMemo<Edge[]>(() => {
    const present = new Set(layout.placed.map((p) => p.id))
    const hl = highlight
    const hlSet = hl ? new Set([...hl.sources, ...Object.keys(hl.affected)]) : null
    return topology.edges.filter((e) => present.has(e.source) && present.has(e.target)).map((e) => {
      const inPath = hlSet?.has(e.source) && hlSet.has(e.target)
      const tStatus = hl?.affected[e.target]?.status
      const liveT = live[e.target]?.status
      let stroke = e.cross_region ? '#6d7ff0' : '#25426b'
      let width = e.cross_region ? 1.4 : 1.1
      let opacity = 0.9
      let animated = false
      if (hlSet) {
        if (inPath) { stroke = STATUS_COLOR[tStatus ?? 'at_risk']; width = 2; animated = true }
        else opacity = 0.12
      } else if (liveT && liveT !== 'ok' && live[e.source]?.status !== 'ok') {
        stroke = STATUS_COLOR[liveT]; width = 1.6; opacity = 0.75
      }
      return {
        id: e.id, source: e.source, target: e.target, animated, type: 'default', markerEnd: { type: 'arrowclosed' as import('@xyflow/react').MarkerType, color: stroke },
        label: e.cross_region && !compact ? e.label || e.type : undefined,
        labelBgPadding: [4, 2] as [number, number], labelBgBorderRadius: 3,
        style: { stroke, strokeWidth: width, opacity, strokeDasharray: e.cross_region ? '6 4' : undefined },
        zIndex: inPath ? 5 : 0,
      }
    })
  }, [topology, layout, highlight, live, compact])

  useEffect(() => {
    const t = window.setTimeout(() => rf.fitView({ padding: 0.12, minZoom: 0.55, duration: 350 }), 30)
    return () => window.clearTimeout(t)
  }, [layoutKey, rf])

  return (
    <ReactFlow
      nodes={rfNodes} edges={rfEdges} nodeTypes={nodeTypes}
      onNodeClick={(_, n) => { if (n.type === 'comp') onNodeClick(n.id) }}
      onPaneClick={onPaneClick}
      nodesDraggable={false} nodesConnectable={false} elementsSelectable={false}
      minZoom={0.35} maxZoom={2} fitView proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#1b2f4f" />
      <Controls position="top-right" showInteractive={false} />
      {false && !compact && <MinimapPanel />}
    </ReactFlow>
  )
}

/** Cloud-console style minimap: titled card with region legend, status-tinted nodes and a blue viewport. */
function MinimapPanel() {
  return (
    <>
      <div className="pointer-events-none absolute bottom-[184px] right-[15px] z-10 flex w-[248px] items-center justify-between rounded-t-lg border border-b-0 border-line-strong bg-ink-800/95 px-2.5 py-1.5 backdrop-blur">
        <span className="text-[10.5px] font-semibold uppercase tracking-wider text-sky">Overview map</span>
        <span className="flex items-center gap-2">
          {Object.entries(REGION_COLOR).map(([r, c]) => (
            <span key={r} className="flex items-center gap-1 text-[9.5px] text-muted">
              <span className="size-1.5 rounded-sm" style={{ background: c }} />{r === 'eu-west' ? 'EU' : r.split('-')[1]}
            </span>
          ))}
        </span>
      </div>
      <MiniMap
        pannable zoomable position="bottom-right"
        bgColor="#081223" maskColor="rgba(5, 11, 22, 0.66)" maskStrokeColor="#4c8df6" maskStrokeWidth={2.5}
        nodeBorderRadius={3} nodeStrokeWidth={0}
        nodeColor={(n) => {
          if (n.type === 'region') return `${REGION_COLOR[(n.data as RegionData).region] ?? '#4c8df6'}22`
          const d = n.data as CompData
          if (d.impact === 'source') return '#4c8df6'
          if (d.impact) return STATUS_COLOR[d.impact]
          const s = d.st?.maintenance ? 'maintenance' : d.st?.status ?? 'ok'
          return s === 'ok' ? `${REGION_COLOR[d.node.region] ?? '#4c8df6'}aa` : STATUS_COLOR[s]
        }}
        style={{ width: 248, height: 168, border: '1px solid #27436b', borderRadius: '0 0 8px 8px', margin: 15, marginTop: 0 }}
      />
    </>
  )
}

export default function TopologyGraph(props: Props) {
  return (
    <ReactFlowProvider>
      <Inner {...props} />
    </ReactFlowProvider>
  )
}
