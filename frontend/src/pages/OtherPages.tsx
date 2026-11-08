import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, ClipboardCheck, FileText, ListChecks, Zap } from 'lucide-react'
import { useApp } from '../lib/ctx'
import { fmtEta, hhmm } from '../lib/api'
import type { Handoff, HandoffItem, Incident } from '../lib/types'
import { Avatar, PageHeader } from '../components/Shell'
import { AiBadge, IncidentCard, MigrationCard, Timeline, catColor } from '../components/Panels'
import { Button, Card, Countdown, Empty, Markdown, PriorityBadge, Stat, Tag } from '../components/ui'
import { EscalationLadder, PriorityBreakdown, StatusBadge } from '../components/IncidentDrawer'
import TopologyGraph from '../components/graph/TopologyGraph'
import { blastToHighlight } from './ConsolePage'

// ============================================================== incidents
export function IncidentsPage() {
  const { state, setOpenIncident } = useApp()
  const [showResolved, setShowResolved] = useState(true)
  const list = state.incidents.filter((i) => (showResolved || i.status !== 'resolved'))
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader crumbs={['datasurge', 'Operations', 'Incidents']} title="Incidents"
        actions={<label className="flex items-center gap-1.5 text-[12px] text-muted"><input type="checkbox" className="accent-brand" checked={showResolved} onChange={(e) => setShowResolved(e.target.checked)} /> Show resolved & merged</label>}>
        <div className="grid grid-cols-4 gap-2">
          <Stat label="Raw alert events" value={state.stats.raw_events} />
          <Stat label="De-duplicated alerts" value={state.stats.alerts} />
          <Stat label="Incidents" value={state.stats.incidents} color="#8ab4f8" />
          <Stat label="Noise reduction" value={`${state.stats.noise_reduction_pct}%`} color="#34d399" />
        </div>
      </PageHeader>
      <div className="min-h-0 flex-1 overflow-auto p-3">
        <Card title={`Incidents (${list.length})`} info="Click a row for routing, escalation, blast radius, AI summary, runbook and notes.">
          <table className="w-full text-[12px]">
            <thead className="bg-ink-800 text-left text-[10.5px] uppercase tracking-wider text-muted">
              <tr>{['Priority', 'ID', 'Title', 'Category', 'Region', 'Status', 'Owner', 'Alerts', 'Impact', 'Age', 'Escalation'].map((h) => <th key={h} className="px-3 py-2 font-semibold">{h}</th>)}</tr>
            </thead>
            <tbody>
              {!list.length && <tr><td colSpan={11}><Empty>No incidents yet.</Empty></td></tr>}
              {list.map((i) => (
                <tr key={i.id} onClick={() => setOpenIncident(i.id)} className={`cursor-pointer border-t border-line hover:bg-ink-800 ${i.status === 'resolved' ? 'opacity-55' : ''}`}>
                  <td className="px-3 py-2"><PriorityBadge p={i.priority} score={i.score} /></td>
                  <td className="px-3 py-2 font-mono text-sky">{i.id}</td>
                  <td className="max-w-[380px] truncate px-3 py-2">{i.title}</td>
                  <td className="px-3 py-2"><Tag color={catColor(i.category)}>{i.category}</Tag></td>
                  <td className="px-3 py-2 text-muted">{i.region}</td>
                  <td className="px-3 py-2"><StatusBadge status={i.status} /></td>
                  <td className="px-3 py-2">{i.assignee_name}</td>
                  <td className="px-3 py-2 font-mono text-muted">{i.raw_count}→{i.alert_count}</td>
                  <td className="px-3 py-2 text-degraded">{i.status === 'resolved' ? '—' : i.blast.earliest_eta === 0 ? 'now' : fmtEta(i.blast.earliest_eta)}</td>
                  <td className="px-3 py-2 text-muted">{Math.round(i.age_min)}m</td>
                  <td className="px-3 py-2">{i.status === 'open' ? (i.esc_level >= 3 ? <span className="text-down">lead paged</span> : <Countdown minutes={i.next_esc_in} total={i.ack_timeout_min} />) : <span className="text-faint">acked {hhmm(i.acked_at)}</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      </div>
    </div>
  )
}

// ============================================================= migrations
export function MigrationsPage() {
  const { state, act } = useApp()
  const groups = [
    { title: 'Awaiting approval', items: state.migrations.filter((m) => m.status === 'suggested' || m.status === 'no_target') },
    { title: 'In progress', items: state.migrations.filter((m) => m.status === 'in_progress') },
    { title: 'History', items: state.migrations.filter((m) => !['suggested', 'in_progress', 'no_target'].includes(m.status)) },
  ]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader crumbs={['datasurge', 'Operations', 'Workload handoff']} title="Smart workload & data handoff"
        actions={
          <label className="flex cursor-pointer items-center gap-2 rounded-md border border-line-strong bg-ink-800 px-3 py-1.5 text-[12px]">
            <Zap size={14} className={state.auto_mode ? 'text-maint' : 'text-faint'} />
            Auto-approve low-risk moves
            <button onClick={() => act('/migrations/auto', { enabled: !state.auto_mode }, `Auto-mode ${state.auto_mode ? 'off' : 'on'}`)}
              className={`relative h-5 w-9 rounded-full transition-colors ${state.auto_mode ? 'bg-brand' : 'bg-ink-600'}`}>
              <span className={`absolute top-0.5 size-4 rounded-full bg-white transition-all ${state.auto_mode ? 'left-[18px]' : 'left-0.5'}`} />
            </button>
          </label>
        }>
        <p className="max-w-3xl text-[12px] text-muted">
          When a host or storage cluster is degraded or forecast to fail, datasurge picks healthy capacity with the right GPU type, enough free GPUs,
          allowed data residency and acceptable latency — preferring the same region — and explains why. Training jobs are checkpointed before moving;
          inference traffic is drained gradually. Every step lands in the timeline.
        </p>
      </PageHeader>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 xl:grid-cols-3">
        {groups.map((g) => (
          <Card key={g.title} title={`${g.title} (${g.items.length})`} bodyClass="space-y-2 overflow-y-auto p-2" className="min-h-[300px]">
            {!g.items.length && <Empty>Nothing here.</Empty>}
            {g.items.map((m) => <MigrationCard key={m.id} m={m} />)}
          </Card>
        ))}
      </div>
    </div>
  )
}

// ================================================================ handoff
const KIND_META: Record<HandoffItem['kind'], { label: string; color: string }> = {
  incident: { label: 'Open incidents', color: '#f43f5e' },
  watch: { label: 'Things to watch', color: '#facc15' },
  migration: { label: 'Pending migrations', color: '#4c8df6' },
  commitment: { label: 'Promises to other teams', color: '#fb923c' },
}

export function HandoffPage() {
  const { state, act } = useApp()
  const [sel, setSel] = useState<string | null>(null)
  const report = state.handoffs.find((h) => h.id === sel) ?? state.handoffs[0]
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader crumbs={['datasurge', 'Operations', 'Shift handoff']} title="Shift handoff"
        actions={<>
          <span className="text-[12px] text-muted">{state.clock.shift.name} ends in <b className="text-white">{fmtEta(state.clock.shift.next_change_in_min)}</b> — a report is generated automatically at shift change</span>
          <Button variant="primary" onClick={() => act('/handoff/generate', {}, 'Handoff report generated')}><FileText size={14} /> Generate handoff now</Button>
        </>} />
      <div className="flex min-h-0 flex-1 gap-3 p-3">
        <Card title="Reports" className="w-64 shrink-0" bodyClass="overflow-y-auto p-2 space-y-1.5">
          {!state.handoffs.length && <Empty>No handoffs yet. Speed up the clock or generate one now.</Empty>}
          {state.handoffs.map((h) => {
            const done = h.items.filter((i) => i.acked_by).length
            return (
              <button key={h.id} onClick={() => setSel(h.id)}
                className={`w-full rounded-md border px-2.5 py-2 text-left ${report?.id === h.id ? 'border-brand bg-brand/10' : 'border-line hover:bg-ink-800'}`}>
                <div className="flex items-center gap-1.5 text-[12px] font-medium">{h.id} {h.complete ? <CheckCircle2 size={13} className="text-ok" /> : h.overdue_notified ? <AlertTriangle size={13} className="text-down" /> : null}</div>
                <div className="text-[11px] text-muted">{h.from_shift} → {h.to_shift}</div>
                <div className="mt-1 flex items-center gap-2 text-[10.5px] text-faint">{hhmm(h.created)} · {done}/{h.items.length} acked</div>
              </button>
            )
          })}
        </Card>
        {report ? <HandoffReport r={report} /> : <Card className="flex-1"><Empty>No handoff report yet.</Empty></Card>}
      </div>
    </div>
  )
}

function HandoffReport({ r }: { r: Handoff }) {
  const { act, state, viewer } = useApp()
  const done = r.items.filter((i) => i.acked_by).length
  const pct = r.items.length ? Math.round((100 * done) / r.items.length) : 100
  const me = state.engineers.find((e) => e.id === viewer)
  const incoming = me?.shift === r.to_shift_id
  const age = state.clock.now_min - r.created_min
  return (
    <div className="flex min-w-0 flex-1 gap-3">
      <Card title={<span className="flex items-center gap-2">{r.id} · {r.from_shift} → {r.to_shift} <AiBadge source={r.narrative_source} model={r.model} reason={r.fallback_reason} /></span>}
        className="min-w-0 flex-1" bodyClass="overflow-y-auto p-4"
        actions={r.narrative_pending ? <span className="blink text-[11px] text-sky">Claude is writing…</span> : null}>
        <div className="mb-3 text-[11.5px] text-muted">Created {hhmm(r.created)} · outgoing lead {r.outgoing_lead} · incoming lead {r.incoming_lead} · {r.reason}</div>
        <Markdown text={r.narrative} />
      </Card>
      <Card title="Acknowledge each item" info="The incoming engineer must acknowledge every item, so nothing is lost between shifts. Unacknowledged items escalate to the incoming lead after 15 min."
        className="w-[440px] shrink-0" bodyClass="overflow-y-auto p-3 space-y-3">
        <div>
          <div className="flex items-center justify-between text-[12px]">
            <span>{done}/{r.items.length} acknowledged</span>
            {r.complete ? <span className="text-ok">Handoff complete</span> : r.overdue_notified ? <span className="text-down">Overdue — escalated to {r.incoming_lead}</span> : <span className="text-faint">{Math.max(0, Math.round(15 - age))} min until escalation</span>}
          </div>
          <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-ink-700"><div className="h-full rounded-full bg-ok transition-all" style={{ width: `${pct}%` }} /></div>
          {!incoming && !r.complete && <div className="mt-2 rounded-md border border-risk/40 bg-risk/5 px-2.5 py-1.5 text-[11.5px] text-risk">You're viewing as {me?.name} ({me?.shift} shift). Switch to an incoming {r.to_shift} engineer (top-right) to acknowledge as them.</div>}
        </div>
        {(Object.keys(KIND_META) as HandoffItem['kind'][]).map((k) => {
          const items = r.items.filter((i) => i.kind === k)
          return (
            <div key={k}>
              <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-wider" style={{ color: KIND_META[k].color }}>
                {KIND_META[k].label} ({items.length})
              </div>
              {!items.length && <div className="text-[11.5px] text-faint">None</div>}
              <div className="space-y-1.5">
                {items.map((i) => (
                  <div key={i.id} className={`rounded-md border px-2.5 py-2 ${i.acked_by ? 'border-ok/30 bg-ok/5' : r.overdue_notified ? 'border-down/50 bg-down/5' : 'border-line bg-ink-900'}`}>
                    <div className="text-[12px] font-medium leading-snug">{i.title}</div>
                    <div className="mt-0.5 text-[11.5px] text-muted">{i.detail}</div>
                    <div className="mt-1.5 flex items-center">
                      {i.acked_by ? (
                        <span className="flex items-center gap-1 text-[11px] text-ok"><CheckCircle2 size={12} /> {i.acked_by_name} · {hhmm(i.acked_at)}</span>
                      ) : (
                        <Button size="sm" variant="primary" className="ml-auto" onClick={() => act(`/handoff/${r.id}/items/${i.id}/ack`, {})}>
                          <ClipboardCheck size={12} /> Acknowledge handoff
                        </Button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </Card>
    </div>
  )
}

// ================================================================ on-call
export function OnCallPage() {
  const { state, setViewer, setPage } = useApp()
  const shifts = ['night', 'day', 'swing']
  const SK: Record<string, string> = { power: '#f59e0b', cooling: '#22d3ee', network: '#a78bfa', storage: '#34d399', gpu: '#f472b6' }
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader crumbs={['datasurge', 'People', 'On-call roster']} title="On-call roster & routing">
        <div className="flex flex-wrap gap-2 text-[11.5px] text-muted">
          <span>Routing: incident category → on-shift engineer with that <b className="text-text">primary</b> specialization and the lowest load; backup = next best (primary or secondary skill); lead last.</span>
          <span className="flex gap-1">Ack windows: {['P1', 'P2', 'P3', 'P4'].map((p) => <Tag key={p}>{p} · {({ P1: 3, P2: 8, P3: 15, P4: 30 } as Record<string, number>)[p]}m/step</Tag>)}</span>
        </div>
      </PageHeader>
      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 overflow-y-auto p-3 lg:grid-cols-3">
        {shifts.map((s) => {
          const engs = state.engineers.filter((e) => e.shift === s)
          const live = engs[0]?.on_shift
          return (
            <Card key={s} title={<span className="flex items-center gap-2 capitalize">{s} shift {live && <Tag color="#34d399">on duty</Tag>}</span>}
              className={live ? 'ring-1 ring-brand/40' : ''} bodyClass="p-2 space-y-1.5">
              {engs.map((e) => (
                <div key={e.id} className="flex items-center gap-2.5 rounded-md border border-line bg-ink-900 px-2.5 py-2">
                  <Avatar name={e.name} size={28} tone={e.on_shift ? '#1a73e8' : '#2e5487'} />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5 text-[12.5px] font-medium">{e.name}{e.role === 'lead' && <Tag color="#8ab4f8">lead</Tag>}</div>
                    <div className="mt-0.5 flex gap-1">
                      {e.skills.map((k, i) => <span key={k} className="rounded px-1.5 text-[10px]" style={{ color: SK[k], background: `${SK[k]}${i === 0 ? '26' : '10'}`, border: `1px solid ${SK[k]}${i === 0 ? '66' : '22'}` }}>{k}{i === 0 ? ' ★' : ''}</span>)}
                    </div>
                  </div>
                  {e.on_shift && (
                    <div className="w-24 text-right">
                      <div className="text-[10px] uppercase tracking-wider text-faint">load {e.load}</div>
                      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink-700"><div className="h-full bg-brand-hi" style={{ width: `${Math.min(100, e.load * 12)}%` }} /></div>
                      <div className="mt-0.5 text-[10.5px] text-muted">{e.open_incidents.length} incident(s)</div>
                    </div>
                  )}
                  <Button size="sm" variant="ghost" onClick={() => { setViewer(e.id); setPage('myview') }}>View as</Button>
                </div>
              ))}
            </Card>
          )
        })}
      </div>
    </div>
  )
}

// ================================================================ my view
export function MyViewPage() {
  const { state, topology, viewer, act } = useApp()
  const me = state.engineers.find((e) => e.id === viewer)
  const mine = state.incidents.filter((i) => i.status !== 'resolved' && (i.assignee === viewer || i.responders.includes(viewer)))
  const others = state.incidents.filter((i) => i.status !== 'resolved' && !mine.includes(i) && !i.title.startsWith('[merged')).length
  const [sel, setSel] = useState<string | null>(null)
  const inc: Incident | undefined = mine.find((i) => i.id === sel) ?? mine[0]

  const focusIds = useMemo(() => {
    if (!inc) return null
    const parents: Record<string, string[]> = {}
    topology.edges.forEach((e) => (parents[e.target] ??= []).push(e.source))
    const ids = new Set<string>([inc.root])
    let frontier = [inc.root]
    for (let d = 0; d < 2; d++) {
      const next: string[] = []
      frontier.forEach((n) => (parents[n] ?? []).forEach((p) => { if (!ids.has(p)) { ids.add(p); next.push(p) } }))
      frontier = next
    }
    inc.blast.affected?.forEach((a) => ids.add(a.id))
    return ids
  }, [inc, topology])
  const migrations = inc ? state.migrations.filter((m) => m.incident_id === inc.id && ['suggested', 'in_progress', 'no_target'].includes(m.status)) : []
  const [checked, setChecked] = useState<Record<string, boolean>>({})

  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader crumbs={['datasurge', 'People', 'My view']} title={`Right info, right time — ${me?.name ?? ''}`}
        actions={me && <span className="flex items-center gap-2 text-[12px] text-muted">
          <Avatar name={me.name} /> {me.role === 'lead' ? 'Shift lead' : `${me.skills[0]} specialist`} · {me.shift} shift
          {me.on_shift ? <Tag color="#34d399">on shift</Tag> : <Tag color="#64748b">off shift</Tag>}
        </span>}>
        <div className="text-[12px] text-muted">
          Showing only incidents routed to you, the part of the graph that matters for them, and the runbook to follow.
          {others > 0 && <span className="text-faint"> {others} other open incident(s) are handled by teammates.</span>}
        </div>
      </PageHeader>
      {!mine.length ? (
        <div className="flex-1 p-6"><Card><div className="flex flex-col items-center gap-2 py-12 text-center">
          <CheckCircle2 size={28} className="text-ok" />
          <div className="text-[14px] font-semibold">Nothing needs you right now</div>
          <div className="text-[12px] text-muted">When an incident in your specialization ({me?.skills.join(', ')}) is routed to you, it appears here with its countdown, graph and runbook.</div>
        </div></Card></div>
      ) : (
        <div className="flex min-h-0 flex-1 gap-3 p-3">
          <div className="w-[330px] shrink-0 space-y-2 overflow-y-auto">
            {mine.map((i) => <IncidentCard key={i.id} inc={i} focused={inc?.id === i.id} onFocus={(id) => id && setSel(id)} />)}
          </div>
          {inc && (
            <div className="flex min-w-0 flex-1 flex-col gap-3">
              <div className="flex min-h-0 flex-1 gap-3">
                <section className="relative min-w-0 flex-1 overflow-hidden rounded-lg border border-line bg-ink-900">
                  <div className="absolute left-3 top-2 z-10 flex items-center gap-2 rounded-md bg-ink-850/90 px-2 py-1 text-[11.5px]">
                    <PriorityBadge p={inc.priority} score={inc.score} /> <span className="font-medium">{inc.root_name}</span>
                    <span className="text-faint">upstream context + blast radius</span>
                  </div>
                  <TopologyGraph topology={topology} nodes={state.nodes} highlight={blastToHighlight({ ...inc.blast, sources: [inc.root] })}
                    selected={[inc.root]} onNodeClick={() => {}} focusIds={focusIds} compact />
                </section>
                <div className="flex w-[360px] shrink-0 flex-col gap-3 overflow-y-auto">
                  <Card title="What to do now" bodyClass="p-3 space-y-3">
                    {inc.status === 'open' && (
                      <div className="flex items-center gap-2 rounded-md border border-down/40 bg-down/5 px-3 py-2">
                        <span className="text-[12px]">Acknowledge before escalation</span>
                        <span className="ml-auto"><Countdown minutes={inc.next_esc_in} total={inc.ack_timeout_min} /></span>
                        <Button size="sm" variant="primary" onClick={() => act(`/incidents/${inc.id}/ack`, {}, 'Acknowledged')}>Ack</Button>
                      </div>
                    )}
                    <EscalationLadder inc={inc} />
                    <ul className="space-y-1 text-[12px]">{inc.blast.statements?.slice(0, 4).map((s, i) => <li key={i} className="rounded bg-ink-900 px-2 py-1">{s}</li>)}</ul>
                    <div className="flex gap-2">
                      {!inc.repair_dispatched && <Button size="sm" onClick={() => act(`/incidents/${inc.id}/repair`, {}, 'Repair dispatched')}>Dispatch repair</Button>}
                      <Button size="sm" onClick={() => act(`/incidents/${inc.id}/resolve`, {}, 'Resolved')}>Resolve</Button>
                    </div>
                  </Card>
                  {inc.runbook && (
                    <Card title={<span className="flex items-center gap-1.5"><ListChecks size={14} /> Suggested runbook</span>} bodyClass="p-3">
                      <div className="mb-2 text-[12px] font-medium text-sky">{inc.runbook.title}</div>
                      <ol className="space-y-1">
                        {inc.runbook.steps.map((s, i) => (
                          <li key={i}><label className="flex cursor-pointer gap-2 text-[11.5px] leading-snug">
                            <input type="checkbox" className="mt-0.5 accent-brand" checked={!!checked[`${inc.id}-${i}`]} onChange={(e) => setChecked({ ...checked, [`${inc.id}-${i}`]: e.target.checked })} />
                            <span className={checked[`${inc.id}-${i}`] ? 'text-faint line-through' : ''}>{s}</span>
                          </label></li>
                        ))}
                      </ol>
                    </Card>
                  )}
                  <Card title="Why this priority" bodyClass="p-3"><PriorityBreakdown inc={inc} /></Card>
                </div>
              </div>
              <div className="grid h-[250px] shrink-0 grid-cols-2 gap-3">
                <Card title={`Suggested handoffs (${migrations.length})`} bodyClass="space-y-2 overflow-y-auto p-2">
                  {!migrations.length && <Empty>No workload moves needed for this incident.</Empty>}
                  {migrations.map((m) => <MigrationCard key={m.id} m={m} />)}
                </Card>
                <Timeline incident={inc.id} title="Incident timeline" />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
