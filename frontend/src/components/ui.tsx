import type { ReactNode } from 'react'
import {
  BatteryCharging, BrainCircuit, Cpu, Database, Fan, Globe, Info, Network, Router, Server, Snowflake, Zap,
} from 'lucide-react'
import type { Kind } from '../lib/types'

export const STATUS_COLOR: Record<string, string> = {
  ok: '#34d399', at_risk: '#facc15', degraded: '#fb923c', down: '#f43f5e', maintenance: '#a78bfa',
}
export const STATUS_LABEL: Record<string, string> = {
  ok: 'Healthy', at_risk: 'At risk', degraded: 'Degraded', down: 'Down', maintenance: 'Maintenance',
}
export const REGION_COLOR: Record<string, string> = {
  'us-east': '#4c8df6', 'us-central': '#22c3ee', 'eu-west': '#818cf8',
}
export const KIND_LABEL: Record<Kind, string> = {
  power_feed: 'Utility feed', ups: 'UPS', chiller: 'Chiller', crac: 'CRAC', spine: 'Spine switch',
  leaf: 'ToR leaf', rack: 'GPU rack', gpu_node: 'GPU node', storage: 'Storage', workload: 'Workload',
}

export function KindIcon({ kind, wtype, size = 14, className = '' }: { kind: Kind; wtype?: string; size?: number; className?: string }) {
  const p = { size, className, strokeWidth: 1.8 }
  switch (kind) {
    case 'power_feed': return <Zap {...p} />
    case 'ups': return <BatteryCharging {...p} />
    case 'chiller': return <Snowflake {...p} />
    case 'crac': return <Fan {...p} />
    case 'spine': return <Network {...p} />
    case 'leaf': return <Router {...p} />
    case 'rack': return <Server {...p} />
    case 'gpu_node': return <Cpu {...p} />
    case 'storage': return <Database {...p} />
    case 'workload': return wtype === 'inference' ? <Globe {...p} /> : <BrainCircuit {...p} />
  }
}

export function StatusDot({ status, size = 8, pulse = false }: { status: string; size?: number; pulse?: boolean }) {
  return (
    <span
      className={`inline-block shrink-0 rounded-full ${pulse && status !== 'ok' ? 'blink' : ''}`}
      style={{ width: size, height: size, background: STATUS_COLOR[status] ?? '#64748b' }}
    />
  )
}

export function StatusPill({ status }: { status: string }) {
  const c = STATUS_COLOR[status] ?? '#64748b'
  return (
    <span className="inline-flex items-center gap-1.5 rounded px-1.5 py-0.5 text-[11px] font-medium"
      style={{ background: `${c}1f`, color: c, border: `1px solid ${c}55` }}>
      <StatusDot status={status} size={6} /> {STATUS_LABEL[status] ?? status}
    </span>
  )
}

const PRIO: Record<string, string> = { P1: '#f43f5e', P2: '#fb923c', P3: '#facc15', P4: '#64748b' }
export function PriorityBadge({ p, score }: { p: string; score?: number }) {
  const c = PRIO[p] ?? '#64748b'
  return (
    <span className="inline-flex items-center overflow-hidden rounded text-[11px] font-semibold"
      style={{ border: `1px solid ${c}88` }}>
      <span className="px-1.5 py-0.5 text-ink-950" style={{ background: c }}>{p}</span>
      {score !== undefined && <span className="px-1.5 py-0.5 font-mono" style={{ color: c }}>{score}</span>}
    </span>
  )
}

const RISK: Record<string, string> = { low: '#34d399', medium: '#facc15', high: '#f43f5e' }
export function RiskBadge({ risk }: { risk: string }) {
  const c = RISK[risk] ?? '#64748b'
  return <span className="rounded px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide"
    style={{ color: c, background: `${c}1a`, border: `1px solid ${c}55` }}>{risk} risk</span>
}

export function Tag({ children, color = '#8ab4f8' }: { children: ReactNode; color?: string }) {
  return <span className="rounded px-1.5 py-0.5 text-[10.5px] font-medium uppercase tracking-wide"
    style={{ color, background: `${color}14`, border: `1px solid ${color}40` }}>{children}</span>
}

export function Card({ title, info, actions, children, className = '', bodyClass = '' }: {
  title?: ReactNode; info?: string; actions?: ReactNode; children: ReactNode; className?: string; bodyClass?: string
}) {
  return (
    <section className={`flex min-h-0 flex-col rounded-lg border border-line bg-ink-850 ${className}`}>
      {title !== undefined && (
        <header className="flex items-center gap-2 border-b border-line px-3 py-2">
          <h3 className="text-[13px] font-semibold text-text">{title}</h3>
          {info && (
            <span title={info} className="inline-flex cursor-help items-center gap-0.5 text-[11px] font-medium text-sky">
              <Info size={12} /> Info
            </span>
          )}
          <div className="ml-auto flex items-center gap-1.5">{actions}</div>
        </header>
      )}
      <div className={`min-h-0 flex-1 ${bodyClass}`}>{children}</div>
    </section>
  )
}

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'
const BTN: Record<BtnVariant, string> = {
  primary: 'bg-brand text-white hover:bg-brand-hi border border-brand',
  secondary: 'bg-ink-750 text-sky hover:bg-ink-700 border border-line-strong',
  ghost: 'text-sky hover:bg-ink-750 border border-transparent',
  danger: 'bg-down/90 text-white hover:bg-down border border-down',
  success: 'bg-emerald-600 text-white hover:bg-emerald-500 border border-emerald-500',
}
export function Button({ variant = 'secondary', size = 'md', className = '', ...rest }:
  React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant; size?: 'sm' | 'md' }) {
  const sz = size === 'sm' ? 'h-6 px-2 text-[11.5px]' : 'h-8 px-3 text-[12.5px]'
  return <button {...rest}
    className={`inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${sz} ${BTN[variant]} ${className}`} />
}

export function Countdown({ minutes, total }: { minutes: number | null; total?: number }) {
  if (minutes === null) return <span className="text-faint">—</span>
  const s = Math.max(0, Math.round(minutes * 60))
  const frac = total ? Math.max(0, Math.min(1, minutes / total)) : 1
  const c = frac < 0.34 ? '#f43f5e' : frac < 0.67 ? '#fb923c' : '#facc15'
  return (
    <span className={`font-mono text-[12px] font-semibold tabular-nums ${frac < 0.34 ? 'blink' : ''}`} style={{ color: c }}>
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, '0')}
    </span>
  )
}

/** Tiny markdown: ## headings, - bullets, **bold**, `code`. */
export function Markdown({ text }: { text: string }) {
  const inline = (s: string) =>
    s.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, i) =>
      part.startsWith('**') ? <strong key={i} className="font-semibold text-text">{part.slice(2, -2)}</strong>
        : part.startsWith('`') ? <code key={i} className="rounded bg-ink-700 px-1 font-mono text-[11.5px]">{part.slice(1, -1)}</code>
          : part)
  const out: ReactNode[] = []
  let list: ReactNode[] = []
  const flush = () => { if (list.length) { out.push(<ul key={out.length} className="mb-2 ml-4 list-disc space-y-0.5 marker:text-faint">{list}</ul>); list = [] } }
  text.split('\n').forEach((raw, i) => {
    const line = raw.trimEnd()
    if (/^#{1,4}\s/.test(line)) {
      flush()
      out.push(<h4 key={`h${i}`} className="mb-1 mt-3 text-[11px] font-semibold uppercase tracking-wider text-sky first:mt-0">{line.replace(/^#+\s/, '')}</h4>)
    } else if (/^\s*[-*]\s/.test(line)) {
      list.push(<li key={i}>{inline(line.replace(/^\s*[-*]\s/, ''))}</li>)
    } else if (line.trim()) {
      flush()
      out.push(<p key={i} className="mb-2">{inline(line)}</p>)
    }
  })
  flush()
  return <div className="text-[12.5px] leading-relaxed text-text/90">{out}</div>
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="flex h-full min-h-16 items-center justify-center px-4 py-6 text-center text-[12px] text-faint">{children}</div>
}

export function Stat({ label, value, sub, color }: { label: string; value: ReactNode; sub?: ReactNode; color?: string }) {
  return (
    <div className="min-w-0 rounded-lg border border-line bg-ink-850 px-3 py-2">
      <div className="truncate text-[10.5px] font-medium uppercase tracking-wider text-muted">{label}</div>
      <div className="mt-0.5 text-[20px] font-semibold leading-tight tabular-nums" style={{ color }}>{value}</div>
      {sub && <div className="truncate text-[11px] text-faint">{sub}</div>}
    </div>
  )
}
