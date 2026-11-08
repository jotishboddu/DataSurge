import { useMemo, useRef, useState } from 'react'
import {
  ArrowRight, Bot, CheckCircle2, Clock, DollarSign, Globe2, Layers, ShieldAlert, Wrench, X, Zap,
} from 'lucide-react'
import { useApp } from '../lib/ctx'
import { fmtEta, hhmm, hhmmss } from '../lib/api'
import type { Blast, Incident, Migration, TimelineEvent } from '../lib/types'
import {
  Button, Card, Countdown, Empty, KIND_LABEL, KindIcon, PriorityBadge, RiskBadge, STATUS_COLOR, StatusDot,
  StatusPill, Tag,
} from './ui'
import { Avatar } from './Shell'

const TIER_C: Record<string, string> = { platinum: '#8ab4f8', gold: '#facc15', silver: '#94a3b8' }
const CAT_C: Record<string, string> = { power: '#f59e0b', cooling: '#22d3ee', network: '#a78bfa', storage: '#34d399', gpu: '#f472b6' }
export const catColor = (c: string) => CAT_C[c] ?? '#8ab4f8'

// ============================================================ blast panel
export function BlastPanel({ blast, nodeId, onClose, whatIf, onStartMaintenance, onCancelWhatIf }: {
  blast: Blast | null; nodeId: string | null; onClose: () => void
  whatIf?: string[]; onStartMaintenance?: () => void; onCancelWhatIf?: () => void
}) {
  const { state, nodeById } = useApp()
  const node = nodeId ? nodeById[nodeId] : null
  const st = nodeId ? state.nodes[nodeId] : null
  const migrations = useMemo(() => {
    if (!blast) return []
    const ids = new Set(blast.workloads.map((w) => w.id))
    return state.migrations.filter((m) => ids.has(m.workload) && (m.status === 'suggested' || m.status === 'in_progress'))
  }, [blast, state.migrations])

  const mode = whatIf ? 'what-if' : blast?.mode === 'live' ? 'live' : 'dependency'
  const modeTag = { 'what-if': ['WHAT-IF · MAINTENANCE PREVIEW', '#a78bfa'], live: ['LIVE IMPACT', '#f43f5e'], dependency: ['IF THIS FAILS', '#4c8df6'] }[mode]

  return (
    <div className="slide-in flex max-h-full w-[350px] flex-col overflow-hidden rounded-lg border border-line-strong bg-ink-850/97 shadow-2xl backdrop-blur">
      <div className="flex items-start gap-2 border-b border-line px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Tag color={modeTag[1]}>{modeTag[0]}</Tag>
            <span className="text-[11px] text-muted">Blast radius</span>
          </div>
          <div className="mt-1 truncate text-[14px] font-semibold text-white">
            {whatIf ? (whatIf.length ? whatIf.map((id) => nodeById[id]?.name).join(', ') : 'Select components to take down') : node?.name ?? blast?.source_names.join(', ')}
          </div>
          {node && st && !whatIf && (
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-muted">
              <StatusPill status={st.maintenance ? 'maintenance' : st.status} />
              <span>{KIND_LABEL[node.kind]} · {node.region}</span>
              {st.reason && <span className="truncate text-faint">— {st.reason}</span>}
            </div>
          )}
        </div>
        <button onClick={onClose} className="text-muted hover:text-text"><X size={15} /></button>
      </div>

      <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
        {!blast || (whatIf && !whatIf.length) ? (
          <Empty>{whatIf ? 'Click components on the graph to plan maintenance. Impact previews here before anything changes.' : 'Loading…'}</Empty>
        ) : !blast.affected.length ? (
          <div className="flex items-center gap-2 rounded-md border border-ok/40 bg-ok/5 px-3 py-2 text-[12px] text-ok">
            <CheckCircle2 size={15} /> No downstream impact — redundancy covers this component.
          </div>
        ) : (
          <>
            <div className="grid grid-cols-4 gap-1.5">
              <div className="col-span-1 rounded-md border border-line bg-ink-900 p-2">
                <div className="text-[9.5px] uppercase tracking-wider text-faint">Impact in</div>
                <div className="text-[16px] font-semibold" style={{ color: blast.earliest_eta === 0 ? '#f43f5e' : '#fb923c' }}>
                  {blast.earliest_eta === null ? '—' : blast.earliest_eta === 0 ? 'now' : fmtEta(blast.earliest_eta).replace('~', '')}
                </div>
              </div>
              {(['down', 'degraded', 'at_risk'] as const).map((s) => (
                <div key={s} className="rounded-md border border-line bg-ink-900 p-2">
                  <div className="text-[9.5px] uppercase tracking-wider text-faint">{s.replace('_', ' ')}</div>
                  <div className="text-[16px] font-semibold" style={{ color: STATUS_COLOR[s] }}>{blast.counts[s]}</div>
                </div>
              ))}
            </div>

            <div className="space-y-1">
              {blast.statements.map((s, i) => (
                <div key={i} className="flex gap-2 rounded-md bg-ink-900 px-2.5 py-1.5 text-[12px] leading-snug">
                  <Clock size={13} className="mt-0.5 shrink-0 text-degraded" />
                  <span>{s}</span>
                </div>
              ))}
            </div>

            {blast.cross_region && (
              <div className="flex items-center gap-2 rounded-md border border-[#6d7ff0]/40 bg-[#6d7ff0]/10 px-2.5 py-1.5 text-[11.5px] text-[#c7d2fe]">
                <Globe2 size={14} /> Cross-region effect: {blast.regions.join(' · ')}
              </div>
            )}

            {!!blast.workloads.length && (
              <div>
                <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted">Affected workloads</div>
                <div className="overflow-hidden rounded-md border border-line">
                  {blast.workloads.map((w) => (
                    <div key={w.id} className="flex items-center gap-2 border-b border-line px-2.5 py-1.5 last:border-0">
                      <StatusDot status={w.impact} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-[12px]">{w.name}</div>
                        <div className="text-[10.5px] text-faint">{w.customer} · <span style={{ color: TIER_C[w.tier] }}>{w.tier}</span> · {w.region}</div>
                      </div>
                      <span className="font-mono text-[11px]" style={{ color: STATUS_COLOR[w.impact] }}>{w.eta === 0 ? 'now' : fmtEta(w.eta)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {!!blast.customers.length && (
              <div>
                <div className="mb-1 flex items-center text-[10.5px] font-semibold uppercase tracking-wider text-muted">
                  Customers & SLAs at risk
                  <span className="ml-auto inline-flex items-center gap-0.5 normal-case tracking-normal text-down">
                    <DollarSign size={11} />{blast.penalty_per_hour.toLocaleString()}/hr exposure
                  </span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {blast.customers.map((c) => (
                    <span key={c.name} className="rounded-md border border-line bg-ink-900 px-2 py-1 text-[11px]" title={c.workloads.join(', ')}>
                      <span className="font-medium" style={{ color: TIER_C[c.tier] }}>{c.name}</span>
                      <span className="text-faint"> · SLA {c.sla} · {c.workloads.length} wl</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {!!migrations.length && (
              <div>
                <div className="mb-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted">Suggested handoffs</div>
                <div className="space-y-1.5">{migrations.map((m) => <MigrationMini key={m.id} m={m} />)}</div>
              </div>
            )}

            <details className="group">
              <summary className="cursor-pointer text-[11px] text-sky">All {blast.affected.length} affected components</summary>
              <div className="mt-1.5 space-y-0.5">
                {blast.affected.map((a) => (
                  <div key={a.id} className="flex items-center gap-2 text-[11.5px]">
                    <StatusDot status={a.status === 'ok' ? 'at_risk' : a.status} size={6} />
                    <KindIcon kind={a.kind} size={12} className="text-faint" />
                    <span className="flex-1 truncate">{a.name}</span>
                    <span className="text-faint">{a.region}</span>
                    <span className="w-12 text-right font-mono text-[10.5px] text-muted">{a.eta === 0 ? 'now' : fmtEta(a.eta)}</span>
                  </div>
                ))}
              </div>
            </details>
          </>
        )}

        {node && st && !whatIf && (
          <details>
            <summary className="cursor-pointer text-[11px] text-sky">Live telemetry</summary>
            <div className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-0.5 font-mono text-[11px]">
              {Object.entries(st.metrics).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2"><span className="text-faint">{k}</span><span>{String(v)}</span></div>
              ))}
            </div>
          </details>
        )}
      </div>

      {whatIf && (
        <div className="flex items-center gap-2 border-t border-line px-3 py-2">
          <Button variant="ghost" size="sm" onClick={onCancelWhatIf}>Cancel</Button>
          <Button variant="primary" size="sm" className="ml-auto" disabled={!whatIf.length} onClick={onStartMaintenance}>
            <Wrench size={13} /> Start maintenance
          </Button>
        </div>
      )}
    </div>
  )
}

export function MigrationMini({ m }: { m: Migration }) {
  const { act } = useApp()
  return (
    <div className="rounded-md border border-line bg-ink-900 px-2.5 py-1.5">
      <div className="flex items-center gap-1.5 text-[11.5px]">
        <span className="truncate font-medium">{m.workload_name}</span>
        <ArrowRight size={12} className="shrink-0 text-faint" />
        <span className="truncate text-sky">{m.to_name.split(' ·')[0]}</span>
        <span className="ml-auto shrink-0"><RiskBadge risk={m.risk} /></span>
      </div>
      {m.status === 'suggested' ? (
        <div className="mt-1 flex items-center gap-2">
          <span className="text-[10.5px] text-faint">~{Math.round(m.time_min ?? 0)} min · {m.same_region ? 'same region' : m.to_region}</span>
          <Button size="sm" variant="primary" className="ml-auto" onClick={() => act(`/migrations/${m.id}/approve`, {}, `${m.id} approved`)}>Approve</Button>
        </div>
      ) : (
        <div className="mt-1 h-1 overflow-hidden rounded bg-ink-700"><div className="h-full bg-brand-hi transition-all" style={{ width: `${m.progress_pct}%` }} /></div>
      )}
    </div>
  )
}

// ========================================================= incident queue
export function IncidentQueue({ focused, onFocus, filter }: { focused: string | null; onFocus: (id: string | null) => void; filter?: (i: Incident) => boolean }) {
  const { state } = useApp()
  const [showAll, setShowAll] = useState(false)
  const list = state.incidents.filter((i) => (showAll || i.status !== 'resolved') && !i.title.startsWith('[merged') && (!filter || filter(i)))
  return (
    <Card title="Incident queue" info="Ranked by priority score: severity + blast radius + SLA impact + time to impact + related alerts. Related alerts are de-duplicated and grouped into one incident."
      actions={<button onClick={() => setShowAll(!showAll)} className="text-[11px] text-sky hover:underline">{showAll ? 'Open only' : 'Show resolved'}</button>}
      className="h-full" bodyClass="overflow-y-auto p-2 space-y-2">
      {!list.length && <Empty>No open incidents. Use <b className="mx-1 text-down">Trigger incident</b> to inject a fault.</Empty>}
      {list.map((i) => <IncidentCard key={i.id} inc={i} focused={focused === i.id} onFocus={onFocus} />)}
    </Card>
  )
}

export function IncidentCard({ inc, focused, onFocus }: { inc: Incident; focused?: boolean; onFocus?: (id: string | null) => void }) {
  const { act, setOpenIncident, viewer } = useApp()
  const prioC = { P1: '#f43f5e', P2: '#fb923c', P3: '#facc15', P4: '#64748b' }[inc.priority]
  const open = inc.status === 'open'
  const mine = inc.assignee === viewer || inc.responders.includes(viewer)
  return (
    <div onClick={() => onFocus?.(focused ? null : inc.id)}
      className={`relative cursor-pointer overflow-hidden rounded-lg border bg-ink-800 pl-3 pr-2.5 py-2 transition-colors ${focused ? 'border-brand ring-1 ring-brand/50' : 'border-line hover:border-line-strong'} ${inc.status === 'resolved' ? 'opacity-55' : ''}`}>
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: prioC }} />
      <div className="flex items-center gap-1.5">
        <PriorityBadge p={inc.priority} score={inc.score} />
        <span className="font-mono text-[11px] text-muted">{inc.id}</span>
        <Tag color={catColor(inc.category)}>{inc.category}</Tag>
        <span className="ml-auto text-[10.5px] text-faint">{inc.region}</span>
      </div>
      <div className="mt-1.5 line-clamp-2 text-[12.5px] font-medium leading-snug text-text">{inc.title}</div>
      <div className="mt-1 flex items-center gap-2 text-[11px] text-muted">
        <span title="raw alert occurrences → grouped alerts"><Layers size={11} className="mr-0.5 inline" />{inc.raw_count}→{inc.alert_count} alerts</span>
        {inc.blast.earliest_eta !== null && inc.blast.earliest_eta !== undefined && (
          <span className="text-degraded"><Clock size={11} className="mr-0.5 inline" />impact {inc.blast.earliest_eta === 0 ? 'now' : fmtEta(inc.blast.earliest_eta)}</span>
        )}
        <span className="ml-auto">{Math.round(inc.age_min)}m ago</span>
      </div>
      <div className="mt-2 flex items-center gap-2">
        <Avatar name={inc.assignee_name} size={20} tone={mine ? '#1a73e8' : '#2e5487'} />
        <div className="min-w-0 flex-1 leading-tight">
          <div className="truncate text-[11.5px]">{inc.assignee_name ?? 'Unassigned'}{mine && <span className="ml-1 text-sky">(you)</span>}</div>
          <div className="truncate text-[10.5px] text-faint">
            {inc.status === 'open' ? inc.esc_step : inc.status === 'resolved' ? `Resolved ${hhmm(inc.resolved_at)}` : `${inc.status} · ack ${inc.acked_by_name ?? ''}`}
          </div>
        </div>
        {open && (
          <div className="text-right leading-tight">
            <div className="text-[9.5px] uppercase tracking-wider text-faint">{inc.esc_level >= 3 ? 'overdue' : 'escalates in'}</div>
            {inc.esc_level >= 3 ? <span className="blink text-[12px] font-semibold text-down">LEAD PAGED</span> : <Countdown minutes={inc.next_esc_in} total={inc.ack_timeout_min} />}
          </div>
        )}
      </div>
      {open && inc.esc_level < 3 && inc.next_esc_in !== null && (
        <div className="mt-1.5 flex gap-0.5">
          {[0, 1, 2, 3].map((l) => (
            <span key={l} className="h-1 flex-1 rounded-full" style={{ background: l <= inc.esc_level ? (l === 0 ? '#4c8df6' : '#f43f5e') : '#1c3150' }} />
          ))}
        </div>
      )}
      <div className="mt-2 flex gap-1.5" onClick={(e) => e.stopPropagation()}>
        {open && <Button size="sm" variant="primary" onClick={() => act(`/incidents/${inc.id}/ack`, {}, `${inc.id} acknowledged`)}>Acknowledge</Button>}
        <Button size="sm" onClick={() => setOpenIncident(inc.id)}>Details</Button>
      </div>
    </div>
  )
}

// ================================================================ timeline
const TL_FILTERS: Record<string, (e: TimelineEvent) => boolean> = {
  All: () => true,
  Alerts: (e) => e.kind.startsWith('alert'),
  Actions: (e) => ['ack', 'note', 'commitment', 'watch', 'repair', 'resolved', 'routed', 'maintenance_started', 'maintenance_ended', 'auto_mode'].includes(e.kind),
  Migrations: (e) => e.kind.startsWith('migration') || e.kind.startsWith('job_'),
  Escalations: (e) => ['escalated', 'priority_changed', 'incident_created', 'incident_merged'].includes(e.kind),
  Shift: (e) => e.kind.startsWith('handoff') || e.kind === 'shift_change',
}
const SEV_C: Record<string, string> = { info: '#8ab4f8', warn: '#facc15', crit: '#f43f5e', success: '#34d399' }

export function Timeline({ incident, className = '', title = 'Timeline' }: { incident?: string | null; className?: string; title?: string }) {
  const { state, setOpenIncident } = useApp()
  const [f, setF] = useState('All')
  const [hideNoise, setHideNoise] = useState(true)
  const ref = useRef<HTMLDivElement>(null)
  const events = useMemo(() => {
    let ev = state.timeline.filter(TL_FILTERS[f])
    if (incident) ev = ev.filter((e) => e.incident === incident)
    if (hideNoise && f === 'All' && !incident) ev = ev.filter((e) => !['alert_cleared', 'alert_refired'].includes(e.kind))
    return ev.slice().reverse().slice(0, 200)
  }, [state.timeline, f, incident, hideNoise])
  return (
    <Card className={className} title={<span className="flex items-center gap-2">{title}{incident && <Tag>{incident}</Tag>}</span>}
      info="Every alert, acknowledgment, escalation, migration step, note and resolution is recorded automatically."
      actions={
        <div className="flex items-center gap-1">
          {Object.keys(TL_FILTERS).map((k) => (
            <button key={k} onClick={() => setF(k)}
              className={`rounded px-2 py-0.5 text-[11px] ${f === k ? 'bg-brand/20 font-semibold text-sky' : 'text-muted hover:text-text'}`}>{k}</button>
          ))}
          {!incident && (
            <label className="ml-2 flex items-center gap-1 text-[11px] text-faint">
              <input type="checkbox" checked={hideNoise} onChange={(e) => setHideNoise(e.target.checked)} className="accent-brand" /> hide clears
            </label>
          )}
        </div>
      }
      bodyClass="overflow-y-auto">
      <div ref={ref} className="divide-y divide-line/60">
        {!events.length && <Empty>No events yet.</Empty>}
        {events.map((e) => (
          <div key={e.id} className="flex items-start gap-2.5 px-3 py-1 text-[12px] hover:bg-ink-800/60">
            <span className="w-[54px] shrink-0 pt-px font-mono text-[11px] text-faint">{hhmmss(e.t)}</span>
            <span className="mt-[5px] size-1.5 shrink-0 rounded-full" style={{ background: SEV_C[e.severity] }} />
            <span className="w-[110px] shrink-0 truncate pt-px text-[10.5px] font-medium uppercase tracking-wide" style={{ color: SEV_C[e.severity] }}>{e.kind.replace(/_/g, ' ')}</span>
            <span className="min-w-0 flex-1 leading-snug text-text/90">{e.message}</span>
            {e.incident && !incident && (
              <button onClick={() => setOpenIncident(e.incident)} className="shrink-0 font-mono text-[10.5px] text-sky hover:underline">{e.incident}</button>
            )}
            {e.actor !== 'system' && <span className="shrink-0 text-[10.5px] text-faint">{e.actor_name}</span>}
          </div>
        ))}
      </div>
    </Card>
  )
}

// ============================================================ migration card
export function MigrationCard({ m }: { m: Migration }) {
  const { act, nodeById } = useApp()
  const [target, setTarget] = useState<string | undefined>(undefined)
  const w = nodeById[m.workload]
  const icon = m.kind === 'data' ? 'storage' : 'workload'
  const statusC: Record<string, string> = { suggested: '#facc15', in_progress: '#4c8df6', completed: '#34d399', rejected: '#64748b', failed: '#f43f5e', expired: '#64748b', no_target: '#f43f5e' }
  return (
    <div className="rounded-lg border border-line bg-ink-800 p-3">
      <div className="flex items-center gap-2">
        <span className="grid size-8 place-items-center rounded-md bg-brand/15 text-sky"><KindIcon kind={icon} wtype={w?.wtype} size={16} /></span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="font-mono text-[11px] text-muted">{m.id}</span>
            <Tag color={statusC[m.status]}>{m.status.replace('_', ' ')}</Tag>
            <Tag>{m.kind === 'checkpoint' ? 'checkpoint' : m.kind === 'data' ? 'data move' : m.wtype === 'training' ? 'checkpoint + move' : 'drain + move'}</Tag>
            {m.auto && <Tag color="#a78bfa"><Zap size={9} className="inline" /> auto</Tag>}
            {m.risk && <RiskBadge risk={m.risk} />}
          </div>
          <div className="mt-0.5 truncate text-[13px] font-semibold">{m.workload_name}
            <span className="ml-2 text-[11.5px] font-normal text-faint">{m.customer} · <span style={{ color: TIER_C[m.tier] }}>{m.tier}</span> · {m.gpus} GPUs</span>
          </div>
        </div>
        {m.incident_id && <span className="font-mono text-[11px] text-sky">{m.incident_id}</span>}
      </div>

      <div className="mt-2.5 flex items-center gap-2 rounded-md bg-ink-900 px-3 py-2 text-[12px]">
        <span className="truncate text-muted">{m.from_name}</span>
        <ArrowRight size={14} className="shrink-0 text-sky" />
        <span className="truncate font-medium text-white">{m.to_name}</span>
        {m.to_region && <span className="ml-auto shrink-0 text-[11px]" style={{ color: m.same_region ? '#34d399' : '#facc15' }}>{m.same_region ? 'same region' : `→ ${m.to_region}`}</span>}
      </div>
      <div className="mt-1 flex items-center gap-1.5 text-[11px] text-degraded"><ShieldAlert size={12} /> Trigger: {m.threat}{m.impact_eta > 0 ? ` (impact ~${Math.round(m.impact_eta)} min)` : ''}</div>

      <ul className="mt-2 space-y-0.5 text-[11.5px] text-text/85">
        {m.reasons?.map((r, i) => <li key={i} className="flex gap-1.5"><span className="text-faint">•</span>{r}</li>)}
      </ul>

      {(m.status === 'in_progress' || m.status === 'completed') && m.phases.length > 0 && (
        <div className="mt-2.5">
          <div className="flex gap-1">
            {m.phases.map((p, i) => (
              <div key={p.name} className="flex-1">
                <div className={`h-1.5 rounded-full ${p.done ? 'bg-ok' : i === m.phase_idx && m.status === 'in_progress' ? 'bg-brand-hi blink' : 'bg-ink-700'}`} />
                <div className={`mt-1 truncate text-[10.5px] ${p.done ? 'text-ok' : i === m.phase_idx ? 'text-sky' : 'text-faint'}`}>{p.label} · {p.dur}m</div>
              </div>
            ))}
          </div>
          <div className="mt-1 text-[11px] text-muted">{m.progress_pct}% · approved by {m.approved_by === 'autopilot' ? 'autopilot' : m.approved_by} {m.approved_at ? `at ${hhmm(m.approved_at)}` : ''}</div>
        </div>
      )}

      {m.status === 'suggested' && (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          {m.alternatives.length > 0 && (
            <select value={target ?? m.to ?? ''} onChange={(e) => setTarget(e.target.value)}
              className="h-7 rounded-md border border-line-strong bg-ink-900 px-2 text-[11.5px] text-text">
              <option value={m.to ?? ''}>Best: {m.to_name.split(' ·')[0]} ({m.to_region}) — score {m.score}</option>
              {m.alternatives.map((a) => (
                <option key={a.to} value={a.to}>Alt: {a.to_name.split(' ·')[0]} ({a.to_region}) — {a.risk} risk, ~{Math.round(a.time_min)}m, score {a.score}</option>
              ))}
            </select>
          )}
          <span className="text-[11px] text-faint">{m.cost_delta_hr !== undefined && `${m.cost_delta_hr >= 0 ? '+' : '−'}$${Math.abs(m.cost_delta_hr).toFixed(2)}/hr`}{m.egress_usd ? ` · $${m.egress_usd.toFixed(0)} egress` : ''}</span>
          <div className="ml-auto flex gap-1.5">
            <Button size="sm" variant="ghost" onClick={() => act(`/migrations/${m.id}/reject`, {}, `${m.id} rejected`)}>Reject</Button>
            <Button size="sm" variant="primary" onClick={() => act(`/migrations/${m.id}/approve`, target && target !== m.to ? { target } : {}, `${m.id} approved`)}>
              <CheckCircle2 size={13} /> Approve migration
            </Button>
          </div>
        </div>
      )}
      {m.status === 'no_target' && <div className="mt-2 text-[11.5px] text-down">Blocked — no eligible capacity. Shed lower-tier load or scale down.</div>}
    </div>
  )
}

export function AiBadge({ source, model, reason }: { source: string; model?: string; reason?: string }) {
  return source === 'claude'
    ? <Tag color="#8ab4f8"><Bot size={10} className="mr-0.5 inline" />Claude · {model}</Tag>
    : <Tag color="#94a3b8"><span title={reason}>Template fallback{reason ? ' · offline' : ''}</span></Tag>
}
