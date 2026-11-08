import { useEffect, useMemo, useRef, useState } from 'react'
import {
  AlertOctagon, ArrowRightLeft, Bot, ChevronDown, ClipboardCheck, FastForward, LayoutDashboard, ListChecks,
  Menu, Pause, Play, RotateCcw, Search, Siren, UserRound, Users, Wifi, WifiOff, X,
} from 'lucide-react'
import { useApp, type Page } from '../lib/ctx'
import { api, fmtEta, hhmmss } from '../lib/api'
import type { Kind } from '../lib/types'
import { Button, KIND_LABEL, KindIcon } from './ui'

export function initials(name?: string | null) {
  return (name ?? '?').split(' ').map((s) => s[0]).slice(0, 2).join('')
}

export function Avatar({ name, size = 22, tone = '#1a73e8' }: { name?: string | null; size?: number; tone?: string }) {
  return (
    <span className="inline-grid shrink-0 place-items-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.42, background: tone }}>{initials(name)}</span>
  )
}

// ================================================================= top bar
export function TopBar({ connected, onToggleNav }: { connected: boolean; onToggleNav: () => void }) {
  const { state, topology, setPage, setSelectedNode, toast } = useApp()
  const { clock, llm } = state
  const [trigger, setTrigger] = useState(false)
  const [q, setQ] = useState('')
  const [showResults, setShowResults] = useState(false)

  const results = useMemo(() => {
    if (!q.trim()) return []
    const s = q.toLowerCase()
    return topology.nodes.filter((n) => n.name.toLowerCase().includes(s) || n.id.includes(s)).slice(0, 8)
  }, [q, topology])

  const setSpeed = (speed: number) => api('/sim/speed', { speed }).catch((e) => toast(e.message, 'err'))
  const pause = () => api('/sim/pause', { paused: !clock.paused })
  const skip = (minutes: number) => api('/sim/advance', { minutes }).then(() => toast(`Advanced ${minutes} simulated min`, 'info'))
  const reset = () => { if (confirm('Reset the simulation? All incidents, migrations and handoffs will be cleared.')) api('/sim/reset', {}) }

  return (
    <header className="relative z-30 flex h-12 shrink-0 items-center gap-3 border-b border-brand/40 bg-gradient-to-r from-[#0a1d3d] via-[#0a1832] to-[#0a1630] px-3">
      <button onClick={onToggleNav} className="grid size-8 place-items-center rounded-md text-sky hover:bg-white/5" aria-label="Toggle navigation">
        <Menu size={18} />
      </button>
      <div className="flex items-center gap-2">
        <span className="grid size-7 place-items-center rounded-md bg-brand shadow-[0_0_12px_#1a73e888]">
          <svg viewBox="0 0 32 32" className="size-5"><path d="M5 20l5-8 5 6 4-5 7 8" fill="none" stroke="#fff" strokeWidth="2.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </span>
        <span className="text-[15px] font-semibold tracking-tight text-white">datasurge</span>
        <span className="hidden text-[12.5px] text-muted lg:inline">Operations Console</span>
      </div>
      <span className="hidden items-center gap-1.5 rounded-md border border-line-strong bg-ink-800/70 px-2 py-1 text-[12px] text-sky md:flex">
        <span className="text-faint">Fleet</span> ai-dc-prod <ChevronDown size={13} />
      </span>

      <div className="relative mx-2 hidden max-w-[360px] flex-1 lg:block">
        <Search size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-faint" />
        <input value={q} onChange={(e) => { setQ(e.target.value); setShowResults(true) }}
          onFocus={() => setShowResults(true)} onBlur={() => window.setTimeout(() => setShowResults(false), 150)}
          placeholder="Search components, racks, workloads…"
          className="h-8 w-full rounded-md border border-line-strong bg-ink-900/80 pl-8 pr-3 text-[12.5px] text-text placeholder:text-faint focus:border-brand focus:outline-none" />
        {showResults && results.length > 0 && (
          <div className="absolute left-0 right-0 top-9 overflow-hidden rounded-md border border-line-strong bg-ink-800 shadow-xl">
            {results.map((n) => (
              <button key={n.id} onMouseDown={() => { setSelectedNode(n.id); setPage('console'); setQ('') }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-[12px] hover:bg-ink-700">
                <KindIcon kind={n.kind as Kind} wtype={n.wtype} className="text-sky" />
                <span className="flex-1 truncate">{n.name}</span>
                <span className="text-[11px] text-faint">{KIND_LABEL[n.kind as Kind]} · {n.region}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="ml-auto flex items-center gap-2">
        <div className="hidden items-center gap-2 rounded-md border border-line-strong bg-ink-900/70 py-1 pl-2.5 pr-1.5 xl:flex">
          <div className="leading-tight">
            <div className="font-mono text-[13px] font-semibold text-white tabular-nums">{hhmmss(clock.time)}</div>
            <div className="text-[10px] text-muted">{clock.shift.name} · handoff in {fmtEta(clock.shift.next_change_in_min)}</div>
          </div>
          <div className="ml-1 flex overflow-hidden rounded border border-line-strong">
            {clock.speeds.map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={`px-1.5 py-0.5 font-mono text-[11px] ${clock.speed === s ? 'bg-brand text-white' : 'text-sky hover:bg-ink-700'}`}>{s}×</button>
            ))}
          </div>
          <button onClick={pause} title={clock.paused ? 'Resume' : 'Pause'} className="grid size-6 place-items-center rounded text-sky hover:bg-ink-700">
            {clock.paused ? <Play size={14} /> : <Pause size={14} />}
          </button>
          <button onClick={() => skip(15)} title="Skip ahead 15 simulated minutes" className="grid size-6 place-items-center rounded text-sky hover:bg-ink-700">
            <FastForward size={14} />
          </button>
          <button onClick={reset} title="Reset simulation" className="grid size-6 place-items-center rounded text-sky hover:bg-ink-700">
            <RotateCcw size={13} />
          </button>
        </div>
        <Button variant="danger" onClick={() => setTrigger(true)}><Siren size={14} /> Trigger incident</Button>
        <span title={llm.available ? `Claude connected (${llm.model})` : `LLM offline: ${llm.last_error ?? ''} — template summaries`}
          className={`hidden items-center gap-1 rounded px-1.5 py-1 text-[11px] md:flex ${llm.available ? 'text-ok' : 'text-faint'}`}>
          <Bot size={14} /> {llm.available ? 'Claude' : 'Offline AI'}
        </span>
        <span title={connected ? 'Live' : 'Reconnecting…'} className={connected ? 'text-ok' : 'text-down blink'}>
          {connected ? <Wifi size={15} /> : <WifiOff size={15} />}
        </span>
        <ViewerSwitcher />
      </div>
      {trigger && <TriggerModal onClose={() => setTrigger(false)} />}
    </header>
  )
}

function ViewerSwitcher() {
  const { state, viewer, setViewer } = useApp()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [])
  const me = state.engineers.find((e) => e.id === viewer)
  const groups = ['night', 'day', 'swing']
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-2 rounded-md py-1 pl-1 pr-2 hover:bg-white/5">
        <Avatar name={me?.name} size={26} />
        <div className="hidden text-left leading-tight md:block">
          <div className="text-[12px] font-medium text-white">{me?.name ?? 'Select engineer'}</div>
          <div className="text-[10px] text-muted">{me ? `${me.role === 'lead' ? 'Shift lead' : me.skills[0]} · ${me.shift}${me.on_shift ? ' · on shift' : ''}` : ''}</div>
        </div>
        <ChevronDown size={13} className="text-muted" />
      </button>
      {open && (
        <div className="absolute right-0 top-11 w-72 overflow-hidden rounded-lg border border-line-strong bg-ink-800 shadow-2xl">
          <div className="border-b border-line px-3 py-2 text-[11px] text-muted">View the console as… (actions are recorded under this name)</div>
          <div className="max-h-[420px] overflow-y-auto py-1">
            {groups.map((g) => (
              <div key={g}>
                <div className="px-3 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wider text-faint">{g} shift</div>
                {state.engineers.filter((e) => e.shift === g).map((e) => (
                  <button key={e.id} onClick={() => { setViewer(e.id); setOpen(false) }}
                    className={`flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-ink-700 ${e.id === viewer ? 'bg-brand/15' : ''}`}>
                    <Avatar name={e.name} size={20} tone={e.on_shift ? '#1a73e8' : '#2e5487'} />
                    <span className="flex-1 text-[12px]">{e.name}</span>
                    <span className="text-[10.5px] text-faint">{e.role === 'lead' ? 'lead' : e.skills[0]}</span>
                    {e.on_shift && <span className="size-1.5 rounded-full bg-ok" />}
                  </button>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ============================================================ trigger modal
function TriggerModal({ onClose }: { onClose: () => void }) {
  const { topology, act } = useApp()
  const [preset, setPreset] = useState(topology.presets[0]?.id)
  const p = topology.presets.find((x) => x.id === preset)
  const [target, setTarget] = useState(p?.default_target ?? '')
  useEffect(() => { setTarget(p?.default_target ?? '') }, [preset]) // eslint-disable-line react-hooks/exhaustive-deps
  const targets = topology.nodes.filter((n) => p?.kinds.includes(n.kind))
  const go = async () => {
    const r = await act('/incidents/trigger', { preset, target }, `Injected: ${p?.name}`)
    if (r) onClose()
  }
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-ink-950/70 backdrop-blur-sm" onMouseDown={onClose}>
      <div className="slide-in w-[560px] rounded-xl border border-line-strong bg-ink-850 shadow-2xl" onMouseDown={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <AlertOctagon size={16} className="text-down" />
          <h2 className="text-[14px] font-semibold">Trigger incident</h2>
          <span className="text-[11.5px] text-muted">Inject a fault into the simulated data center</span>
          <button onClick={onClose} className="ml-auto text-muted hover:text-text"><X size={16} /></button>
        </div>
        <div className="grid grid-cols-2 gap-2 p-4">
          {topology.presets.map((x) => (
            <button key={x.id} onClick={() => setPreset(x.id)}
              className={`rounded-lg border p-3 text-left transition-colors ${preset === x.id ? 'border-brand bg-brand/10' : 'border-line hover:border-line-strong hover:bg-ink-800'}`}>
              <div className="flex items-center gap-2 text-[12.5px] font-semibold">
                <KindIcon kind={x.kinds[0]} className="text-sky" /> {x.name}
              </div>
              <div className="mt-1 text-[11.5px] leading-snug text-muted">{x.description}</div>
            </button>
          ))}
        </div>
        <div className="flex items-center gap-3 border-t border-line px-4 py-3">
          <label className="text-[12px] text-muted">Target</label>
          <select value={target} onChange={(e) => setTarget(e.target.value)}
            className="h-8 flex-1 rounded-md border border-line-strong bg-ink-900 px-2 text-[12.5px] text-text focus:border-brand focus:outline-none">
            {targets.map((n) => <option key={n.id} value={n.id}>{n.region} · {n.name}</option>)}
          </select>
          <Button variant="danger" onClick={go}><Siren size={14} /> Inject fault</Button>
        </div>
      </div>
    </div>
  )
}

// ================================================================ side nav
export function SideNav({ collapsed }: { collapsed: boolean }) {
  const { page, setPage, state, viewer } = useApp()
  const openInc = state.incidents.filter((i) => i.status !== 'resolved').length
  const p1 = state.incidents.filter((i) => i.status !== 'resolved' && i.priority === 'P1').length
  const pendingMig = state.migrations.filter((m) => m.status === 'suggested').length
  const handoffPending = state.handoffs.reduce((n, h) => n + h.items.filter((i) => !i.acked_by).length, 0)
  const mine = state.incidents.filter((i) => i.status !== 'resolved' && (i.assignee === viewer || i.responders.includes(viewer))).length

  const items: { id: Page; label: string; icon: React.ReactNode; badge?: number; tone?: string }[][] = [
    [
      { id: 'console', label: 'Operations console', icon: <LayoutDashboard size={16} /> },
      { id: 'incidents', label: 'Incidents', icon: <Siren size={16} />, badge: openInc, tone: p1 ? '#f43f5e' : '#4c8df6' },
      { id: 'migrations', label: 'Workload handoff', icon: <ArrowRightLeft size={16} />, badge: pendingMig, tone: '#facc15' },
      { id: 'handoff', label: 'Shift handoff', icon: <ClipboardCheck size={16} />, badge: handoffPending, tone: '#fb923c' },
    ],
    [
      { id: 'myview', label: 'My view', icon: <UserRound size={16} />, badge: mine, tone: '#4c8df6' },
      { id: 'oncall', label: 'On-call roster', icon: <Users size={16} /> },
    ],
  ]
  const sections = ['Operations', 'People']
  return (
    <nav className={`flex shrink-0 flex-col border-r border-line bg-ink-900 transition-[width] duration-200 ${collapsed ? 'w-14' : 'w-56'}`}>
      {items.map((group, gi) => (
        <div key={gi} className="px-2 pt-3">
          {!collapsed && <div className="px-2 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-faint">{sections[gi]}</div>}
          {group.map((it) => (
            <button key={it.id} onClick={() => setPage(it.id)} title={it.label}
              className={`relative mb-0.5 flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-[12.5px] transition-colors ${page === it.id ? 'bg-brand/15 font-semibold text-white' : 'text-muted hover:bg-ink-800 hover:text-text'}`}>
              {page === it.id && <span className="absolute inset-y-1 left-0 w-[3px] rounded-r bg-brand-hi" />}
              <span className={page === it.id ? 'text-sky' : ''}>{it.icon}</span>
              {!collapsed && <span className="flex-1 truncate text-left">{it.label}</span>}
              {!!it.badge && (
                <span className={`rounded-full px-1.5 text-[10.5px] font-semibold text-ink-950 ${collapsed ? 'absolute right-0.5 top-0.5 text-[9px]' : ''}`}
                  style={{ background: it.tone }}>{it.badge}</span>
              )}
            </button>
          ))}
        </div>
      ))}
      <div className="mt-auto border-t border-line p-3">
        {!collapsed ? (
          <div className="space-y-1 text-[11px] text-faint">
            <div className="flex items-center gap-1.5"><ListChecks size={12} /> {state.stats.raw_events} raw events</div>
            <div>{state.stats.alerts} alerts → {state.stats.incidents} incidents</div>
            <div className="text-sky">{state.stats.noise_reduction_pct}% noise reduction</div>
          </div>
        ) : <ListChecks size={16} className="mx-auto text-faint" />}
      </div>
    </nav>
  )
}

export function Toasts() {
  const { toasts } = useApp()
  return (
    <div className="pointer-events-none fixed bottom-4 left-1/2 z-[60] flex -translate-x-1/2 flex-col items-center gap-2">
      {toasts.map((t) => (
        <div key={t.id} className={`slide-in rounded-md border px-3 py-2 text-[12.5px] shadow-xl ${t.tone === 'err' ? 'border-down/60 bg-[#2a0f1a] text-[#fecdd3]' : t.tone === 'ok' ? 'border-ok/50 bg-[#0b2620] text-[#bbf7d0]' : 'border-line-strong bg-ink-800 text-text'}`}>
          {t.text}
        </div>
      ))}
    </div>
  )
}

export function PageHeader({ crumbs, title, children, actions }: { crumbs: string[]; title: string; children?: React.ReactNode; actions?: React.ReactNode }) {
  return (
    <div className="shrink-0 border-b border-line bg-ink-900/60 px-4 pb-3 pt-2.5">
      <div className="text-[11.5px] text-muted">
        {crumbs.map((c, i) => (
          <span key={i}>{i > 0 && <span className="mx-1.5 text-faint">›</span>}<span className={i < crumbs.length - 1 ? 'text-sky' : ''}>{c}</span></span>
        ))}
      </div>
      <div className="mt-1 flex items-center gap-3">
        <h1 className="text-[19px] font-semibold tracking-tight text-white">{title}</h1>
        <div className="ml-auto flex items-center gap-2">{actions}</div>
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  )
}
