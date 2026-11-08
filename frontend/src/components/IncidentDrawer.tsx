import { useState } from 'react'
import { Bot, CheckCircle2, Hammer, RefreshCw, X } from 'lucide-react'
import { useApp } from '../lib/ctx'
import { hhmm } from '../lib/api'
import type { Incident } from '../lib/types'
import { Button, Countdown, Empty, Markdown, PriorityBadge, Tag } from './ui'
import { AiBadge, MigrationCard, Timeline, catColor } from './Panels'
import { Avatar } from './Shell'

const FACTORS: [string, string, number][] = [
  ['severity', 'Severity', 40], ['blast_radius', 'Blast radius', 20], ['sla_impact', 'SLA impact', 20],
  ['time_to_impact', 'Time to impact', 15], ['related_alerts', 'Related alerts', 10],
]

export function PriorityBreakdown({ inc }: { inc: Incident }) {
  return (
    <div className="space-y-1.5">
      {FACTORS.map(([k, label, max]) => (
        <div key={k} className="flex items-center gap-2 text-[11.5px]">
          <span className="w-28 text-muted">{label}</span>
          <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-ink-700">
            <div className="h-full rounded-full bg-brand-hi" style={{ width: `${(100 * (inc.breakdown[k] ?? 0)) / max}%` }} />
          </div>
          <span className="w-12 text-right font-mono text-[11px] text-text">{inc.breakdown[k] ?? 0}/{max}</span>
        </div>
      ))}
    </div>
  )
}

export function EscalationLadder({ inc }: { inc: Incident }) {
  const steps = [
    { label: 'Notify primary', who: inc.assignee_name },
    { label: 'Re-notify (page + phone)', who: inc.assignee_name },
    { label: 'Backup engineer', who: inc.backup_name },
    { label: 'Shift lead', who: inc.lead ? undefined : '—' },
  ]
  const acked = inc.status !== 'open'
  return (
    <div className="flex gap-1">
      {steps.map((s, i) => {
        const reached = i <= inc.esc_level
        const c = acked ? (reached ? '#34d399' : '#1c3150') : reached ? (i === 0 ? '#4c8df6' : '#f43f5e') : '#1c3150'
        return (
          <div key={i} className="flex-1 rounded-md border px-2 py-1.5" style={{ borderColor: `${c}88`, background: reached ? `${c}14` : 'transparent' }}>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: reached ? c : '#5d7499' }}>Step {i + 1}</div>
            <div className="text-[11px] leading-tight">{s.label}</div>
            {s.who && <div className="truncate text-[10.5px] text-faint">{s.who}</div>}
          </div>
        )
      })}
    </div>
  )
}

export default function IncidentDrawer() {
  const { state, openIncident, setOpenIncident, act, setSelectedNode, setPage } = useApp()
  const inc = state.incidents.find((i) => i.id === openIncident)
  const [tab, setTab] = useState('Overview')
  const [note, setNote] = useState('')
  const [kind, setKind] = useState<'note' | 'commitment' | 'watch'>('note')
  const [checked, setChecked] = useState<Record<string, boolean>>({})
  const [generating, setGenerating] = useState(false)
  if (!inc) return null
  const migrations = state.migrations.filter((m) => m.incident_id === inc.id)
  const tabs = ['Overview', 'Timeline', 'AI summary', 'Runbook', `Notes (${inc.notes.length})`]

  const genSummary = async () => {
    setGenerating(true)
    await act(`/incidents/${inc.id}/summary`, {})
    setGenerating(false)
  }

  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-ink-950/50" onMouseDown={() => setOpenIncident(null)}>
      <aside className="slide-in flex h-full w-[640px] max-w-full flex-col border-l border-line-strong bg-ink-850 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="border-b border-line px-4 pb-2 pt-3">
          <div className="flex items-center gap-2">
            <PriorityBadge p={inc.priority} score={inc.score} />
            <span className="font-mono text-[12px] text-muted">{inc.id}</span>
            <Tag color={catColor(inc.category)}>{inc.category}</Tag>
            <Tag>{inc.region}</Tag>
            <StatusBadge status={inc.status} />
            <button onClick={() => setOpenIncident(null)} className="ml-auto text-muted hover:text-text"><X size={17} /></button>
          </div>
          <h2 className="mt-2 text-[16px] font-semibold leading-snug text-white">{inc.title}</h2>
          <div className="mt-1 text-[11.5px] text-muted">
            Opened {hhmm(inc.created)} · {Math.round(inc.age_min)} min · root <button className="text-sky hover:underline"
              onClick={() => { setSelectedNode(inc.root); setPage('console'); setOpenIncident(null) }}>{inc.root_name}</button>
            {inc.merged_from.length > 0 && <> · merged {inc.merged_from.join(', ')}</>}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {inc.status === 'open' && <Button variant="primary" onClick={() => act(`/incidents/${inc.id}/ack`, {}, 'Acknowledged')}><CheckCircle2 size={14} /> Acknowledge</Button>}
            {inc.status !== 'resolved' && !inc.repair_dispatched && <Button onClick={() => act(`/incidents/${inc.id}/repair`, {}, 'Repair dispatched')}><Hammer size={14} /> Dispatch repair</Button>}
            {inc.status !== 'resolved' && <Button onClick={() => act(`/incidents/${inc.id}/resolve`, {}, 'Resolved')}>Resolve</Button>}
            <Button variant="ghost" onClick={() => { setTab('AI summary'); genSummary() }}><Bot size={14} /> Generate AI summary</Button>
          </div>
          <div className="mt-3 flex gap-4 border-b border-transparent">
            {tabs.map((t) => (
              <button key={t} onClick={() => setTab(t.split(' (')[0])}
                className={`-mb-2 border-b-2 pb-1.5 text-[12.5px] ${tab === t.split(' (')[0] ? 'border-brand-hi font-semibold text-white' : 'border-transparent text-muted hover:text-text'}`}>{t}</button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {tab === 'Overview' && (
            <div className="space-y-4">
              <section>
                <H>Routing & missed-warning protection</H>
                <div className="mb-2 flex items-center gap-3 text-[12px]">
                  <Avatar name={inc.assignee_name} /> <span><b>{inc.assignee_name}</b> <span className="text-faint">primary</span></span>
                  <span className="text-faint">·</span><span>{inc.backup_name ?? '—'} <span className="text-faint">backup</span></span>
                  {inc.status === 'open' && <span className="ml-auto flex items-center gap-2 text-[11px] text-muted">next step in <Countdown minutes={inc.next_esc_in} total={inc.ack_timeout_min} /></span>}
                  {inc.acked_by_name && <span className="ml-auto text-[11.5px] text-ok">Acked by {inc.acked_by_name} at {hhmm(inc.acked_at)}</span>}
                </div>
                <EscalationLadder inc={inc} />
                <div className="mt-1 text-[11px] text-faint">Ack window for {inc.priority}: {inc.ack_timeout_min} simulated min per step.</div>
              </section>
              <section>
                <H>Priority score {inc.score}/100</H>
                <PriorityBreakdown inc={inc} />
              </section>
              <section>
                <H>Blast radius</H>
                {inc.blast.statements?.length ? (
                  <ul className="space-y-1 text-[12px]">{inc.blast.statements.map((s, i) => <li key={i} className="rounded bg-ink-900 px-2.5 py-1.5">{s}</li>)}</ul>
                ) : <div className="text-[12px] text-faint">No downstream impact.</div>}
                {!!inc.blast.customers?.length && (
                  <div className="mt-2 text-[11.5px] text-muted">Customers: {inc.blast.customers.map((c) => `${c.name} (SLA ${c.sla})`).join(', ')} · ${inc.blast.penalty_per_hour.toLocaleString()}/hr exposure</div>
                )}
              </section>
              {!!migrations.length && (
                <section>
                  <H>Workload & data handoff</H>
                  <div className="space-y-2">{migrations.slice(0, 6).map((m) => <MigrationCard key={m.id} m={m} />)}</div>
                </section>
              )}
              <section>
                <H>{inc.alert_count} grouped alerts ({inc.raw_count} raw occurrences)</H>
                <div className="overflow-hidden rounded-md border border-line">
                  {inc.alerts.map((a) => (
                    <div key={a.id} className={`flex items-center gap-2 border-b border-line px-2.5 py-1.5 text-[11.5px] last:border-0 ${a.active ? '' : 'opacity-50'}`}>
                      <span className="size-1.5 rounded-full" style={{ background: { crit: '#f43f5e', warn: '#facc15', info: '#8ab4f8' }[a.severity] }} />
                      <span className="flex-1 truncate">{a.message}</span>
                      {a.count > 1 && <Tag color="#94a3b8">×{a.count}</Tag>}
                      <span className="font-mono text-[10.5px] text-faint">{hhmm(a.first_seen)}</span>
                      <span className="w-12 text-right text-[10.5px]">{a.active ? <span className="text-down">active</span> : <span className="text-ok">clear</span>}</span>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          )}

          {tab === 'Timeline' && <Timeline incident={inc.id} className="h-full" title="Incident timeline" />}

          {tab === 'AI summary' && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                {inc.summary && <AiBadge source={inc.summary.source} model={inc.summary.model} reason={inc.summary.fallback_reason} />}
                {inc.summary && <span className="text-[11px] text-faint">generated {hhmm(inc.summary.generated_at)}</span>}
                {(generating || inc.summary?.pending) && <span className="blink text-[11px] text-sky">Claude is writing…</span>}
                <Button size="sm" className="ml-auto" onClick={genSummary} disabled={generating}><RefreshCw size={12} /> Regenerate</Button>
              </div>
              {inc.summary ? <div className="rounded-lg border border-line bg-ink-900 p-3"><Markdown text={inc.summary.text} /></div>
                : <Empty>No summary yet. Click “Generate AI summary”. Summaries are also generated automatically on resolution.</Empty>}
              {inc.summary?.fallback_reason && <div className="mt-2 text-[11px] text-faint">LLM unavailable ({inc.summary.fallback_reason}) — showing the template summary.</div>}
            </div>
          )}

          {tab === 'Runbook' && (
            inc.runbook ? (
              <div>
                <div className="mb-2 text-[13px] font-semibold">{inc.runbook.title}</div>
                <ol className="space-y-1.5">
                  {inc.runbook.steps.map((s, i) => (
                    <li key={i}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-md border border-line bg-ink-900 px-3 py-2 text-[12px]">
                        <input type="checkbox" className="mt-0.5 accent-brand" checked={!!checked[i]} onChange={(e) => setChecked({ ...checked, [i]: e.target.checked })} />
                        <span className={checked[i] ? 'text-faint line-through' : ''}><span className="mr-1 text-faint">{i + 1}.</span>{s}</span>
                      </label>
                    </li>
                  ))}
                </ol>
              </div>
            ) : <Empty>No runbook for this category.</Empty>
          )}

          {tab === 'Notes' && (
            <div className="space-y-3">
              <div className="rounded-lg border border-line bg-ink-900 p-3">
                <div className="mb-2 flex gap-1">
                  {([['note', 'Note'], ['commitment', 'Promise to another team'], ['watch', 'Thing to watch']] as const).map(([k, l]) => (
                    <button key={k} onClick={() => setKind(k)} className={`rounded px-2 py-0.5 text-[11.5px] ${kind === k ? 'bg-brand/20 text-sky' : 'text-muted hover:text-text'}`}>{l}</button>
                  ))}
                </div>
                <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3}
                  placeholder={kind === 'commitment' ? 'e.g. Told Acme TAM we would send an RCA by 09:00' : kind === 'watch' ? 'e.g. CRAC-2 fan bearing noisy — check at 07:00' : 'What did you see or do?'}
                  className="w-full resize-none rounded-md border border-line-strong bg-ink-850 p-2 text-[12.5px] text-text placeholder:text-faint focus:border-brand focus:outline-none" />
                <div className="mt-2 flex justify-between">
                  <span className="text-[11px] text-faint">Promises and watch items are carried into the shift handoff.</span>
                  <Button size="sm" variant="primary" disabled={!note.trim()} onClick={async () => { await act(`/incidents/${inc.id}/note`, { text: note, kind }, 'Saved'); setNote('') }}>Add</Button>
                </div>
              </div>
              {inc.notes.slice().reverse().map((n, i) => (
                <div key={i} className="rounded-md border border-line px-3 py-2">
                  <div className="flex items-center gap-2 text-[11px] text-muted">
                    <Avatar name={n.author_name} size={18} /> {n.author_name} · {hhmm(n.t)}
                    {n.kind !== 'note' && <Tag color={n.kind === 'commitment' ? '#fb923c' : '#facc15'}>{n.kind}</Tag>}
                  </div>
                  <div className="mt-1 text-[12.5px]">{n.text}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}

function H({ children }: { children: React.ReactNode }) {
  return <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-sky">{children}</h4>
}

export function StatusBadge({ status }: { status: Incident['status'] }) {
  const c = { open: '#f43f5e', acknowledged: '#facc15', mitigating: '#4c8df6', resolved: '#34d399' }[status]
  return <Tag color={c}>{status}</Tag>
}
