import type { Kind, Topology, TopoNode } from '../../lib/types'

export const NODE_W = 220
export const NODE_H = 68
const COL_W = 290
const ROW_H = 100
const PAD_X = 22
const HEADER_H = 54
const BAND_GAP = 36

export const COLUMNS: { label: string; kinds: Kind[] }[] = [
  { label: 'Power · Spine', kinds: ['power_feed', 'spine'] },
  { label: 'UPS · Leaf', kinds: ['ups', 'leaf'] },
  { label: 'Cooling', kinds: ['chiller', 'crac'] },
  { label: 'GPU racks', kinds: ['rack'] },
  { label: 'GPU nodes', kinds: ['gpu_node'] },
  { label: 'Storage', kinds: ['storage'] },
  { label: 'AI workloads', kinds: ['workload'] },
]
const COL_OF: Record<string, number> = {}
COLUMNS.forEach((c, i) => c.kinds.forEach((k) => (COL_OF[k] = i)))

export interface Placed { id: string; x: number; y: number; region: string }
export interface Band { region: string; name: string; y: number; width: number; height: number }

/** Deterministic column layout: one horizontal band per region. */
export function layoutTopology(topo: Topology, include?: Set<string>) {
  const placed: Placed[] = []
  const bands: Band[] = []
  let y = 0
  const width = PAD_X * 2 + (COLUMNS.length - 1) * COL_W + NODE_W
  for (const r of topo.regions) {
    const nodes = topo.nodes.filter((n) => n.region === r.id && (!include || include.has(n.id)))
    if (!nodes.length) continue
    const cols: TopoNode[][] = COLUMNS.map(() => [])
    for (const n of nodes) cols[COL_OF[n.kind] ?? 6].push(n)
    // order inside columns: keep kind order, then id; workloads follow their host's position
    cols.forEach((c, i) => {
      const kinds = COLUMNS[i].kinds
      c.sort((a, b) => kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.id.localeCompare(b.id))
    })
    const gpuIdx = new Map(cols[4].map((g, i) => [g.id, i]))
    cols[6].sort((a, b) => (gpuIdx.get(a.host ?? '') ?? 99) - (gpuIdx.get(b.host ?? '') ?? 99) || a.id.localeCompare(b.id))
    const maxRows = Math.max(...cols.map((c) => c.length))
    const height = HEADER_H + maxRows * ROW_H + 18
    cols.forEach((c, ci) => {
      const offset = ((maxRows - c.length) * ROW_H) / 2
      c.forEach((n, ri) => {
        placed.push({ id: n.id, region: r.id, x: PAD_X + ci * COL_W, y: HEADER_H + offset + ri * ROW_H })
      })
    })
    bands.push({ region: r.id, name: r.name, y, width, height })
    y += height + BAND_GAP
  }
  return { placed, bands, colX: COLUMNS.map((_, i) => PAD_X + i * COL_W) }
}
