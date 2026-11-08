export type Status = 'ok' | 'at_risk' | 'degraded' | 'down'
export type Kind =
  | 'power_feed' | 'ups' | 'chiller' | 'crac' | 'spine' | 'leaf'
  | 'rack' | 'gpu_node' | 'storage' | 'workload'

export interface Forecast { status: Status; eta: number; reason: string }

export interface TopoNode {
  id: string
  name: string
  kind: Kind
  region: string
  gpu_type?: string
  gpus_total?: number
  gpus_used?: number
  gpus?: number
  gpu_types?: string[]
  wtype?: 'training' | 'inference'
  customer?: string
  customer_name?: string
  tier?: string
  host?: string
  storage?: string
  home_region?: string
  latency_budget_ms?: number
  residency?: string[]
  rack?: string
}

export interface TopoEdge {
  id: string
  source: string
  target: string
  type: string
  redundant: boolean
  label: string
  cross_region: boolean
}

export interface Preset { id: string; name: string; description: string; kinds: Kind[]; default_target: string }

export interface Topology {
  version: number
  regions: { id: string; name: string; code: string }[]
  customers: { id: string; name: string; tier: string; sla: string; penalty_per_hour: number }[]
  nodes: TopoNode[]
  edges: TopoEdge[]
  presets: Preset[]
}

export interface NodeState {
  status: Status
  forecast: Forecast | null
  cause: string | null
  reason: string
  own: Status
  maintenance: boolean
  metrics: Record<string, number | string | boolean | null>
}

export interface BlastAffected {
  id: string; name: string; kind: Kind; region: string; status: Status
  forecast: Forecast | null; eta: number | null
}

export interface Blast {
  mode: 'live' | 'hypothetical'
  sources: string[]
  source_names: string[]
  affected: BlastAffected[]
  counts: Record<'at_risk' | 'degraded' | 'down', number>
  workloads: { id: string; name: string; customer: string; tier: string; sla: string; type: string; status: Status; impact: Status; eta: number | null; region: string }[]
  customers: { name: string; tier: string; sla: string; penalty_per_hour: number; workloads: string[] }[]
  statements: string[]
  earliest_eta: number | null
  regions: string[]
  cross_region: boolean
  penalty_per_hour: number
}

export interface Alert {
  id: string; rule: string; node: string; severity: 'info' | 'warn' | 'crit'
  message: string; first_seen: string; last_seen: string; count: number; active: boolean
  incident_id: string | null; region: string
}

export interface Note { t: string; author: string; author_name: string; text: string; kind: 'note' | 'commitment' | 'watch' }

export interface Incident {
  id: string; title: string; root: string; root_name: string
  category: 'power' | 'cooling' | 'network' | 'storage' | 'gpu'
  region: string
  status: 'open' | 'acknowledged' | 'mitigating' | 'resolved'
  priority: 'P1' | 'P2' | 'P3' | 'P4'
  score: number
  breakdown: Record<string, number>
  created: string; age_min: number
  assignee: string | null; assignee_name: string | null
  backup: string | null; backup_name: string | null
  lead: string | null; responders: string[]
  esc_level: number; esc_step: string; next_esc_in: number | null; ack_timeout_min: number
  acked_by: string | null; acked_by_name: string | null; acked_at: string | null
  resolved_at: string | null
  alerts: Alert[]; alert_count: number; active_alerts: number; raw_count: number
  notes: Note[]
  summary: { text: string; source: 'claude' | 'template'; model?: string; generated_at: string; pending: boolean; fallback_reason?: string } | null
  blast: Blast
  merged_from: string[]
  repair_dispatched: boolean
  runbook: { title: string; steps: string[] } | null
}

export interface Phase { name: string; label: string; dur: number; done: boolean }

export interface Migration {
  id: string; kind: 'workload' | 'data' | 'checkpoint'
  workload: string; workload_name: string; wtype: string; customer: string; tier: string; gpus: number
  status: 'suggested' | 'in_progress' | 'approved' | 'completed' | 'rejected' | 'failed' | 'expired' | 'no_target'
  created: string; impact_eta: number; threat: string; incident_id: string | null
  approved_by: string | null; approved_at?: string; auto?: boolean
  from?: string; from_name?: string; to: string | null; to_name: string; to_region?: string; same_region?: boolean
  risk: 'low' | 'medium' | 'high'; risk_reasons?: string[]
  time_min?: number; cost_delta_hr?: number; egress_usd?: number; latency_add_ms?: number; score?: number
  reasons: string[]
  phases: Phase[]; phase_idx: number; progress_pct: number
  alternatives: { to: string; to_name: string; to_region: string; same_region: boolean; score: number; risk: string; time_min: number; cost_delta_hr: number; latency_add_ms: number }[]
  completed_at?: string
}

export interface HandoffItem {
  id: string; kind: 'incident' | 'watch' | 'migration' | 'commitment'
  title: string; detail: string; ref: string | null
  acked_by: string | null; acked_by_name: string | null; acked_at: string | null
}

export interface Handoff {
  id: string; created: string; created_min: number
  from_shift: string; to_shift: string; to_shift_id: string
  outgoing_lead: string | null; incoming_lead: string | null; incoming_lead_id: string | null
  reason: string; items: HandoffItem[]
  narrative: string; narrative_source: 'claude' | 'template'; narrative_pending: boolean
  model?: string; fallback_reason?: string
  complete: boolean; overdue_notified: boolean
}

export interface TimelineEvent {
  id: number; t: string; t_min: number; kind: string
  severity: 'info' | 'warn' | 'crit' | 'success'
  message: string; node: string | null; incident: string | null
  actor: string; actor_name: string; region: string | null
}

export interface Engineer {
  id: string; name: string; shift: string; role: 'lead' | 'engineer'; skills: string[]
  on_shift: boolean; load: number; open_incidents: string[]
}

export interface Shift { id: string; name: string; start: string; end: string; next_change_in_min: number; lead: string | null }

export interface LiveState {
  type: 'state'
  clock: { time: string; now_min: number; speed: number; paused: boolean; speeds: number[]; shift: Shift }
  topology_version: number
  nodes: Record<string, NodeState>
  incidents: Incident[]
  alerts: Alert[]
  migrations: Migration[]
  auto_mode: boolean
  handoffs: Handoff[]
  timeline: TimelineEvent[]
  engineers: Engineer[]
  faults: { id: string; preset: string; target: string; label: string; age_min: number; repair_in: number | null }[]
  stats: { raw_events: number; alerts: number; active_alerts: number; incidents: number; open_incidents: number; noise_reduction_pct: number }
  llm: { available: boolean; model: string; last_error: string | null }
  topology?: Topology
}
