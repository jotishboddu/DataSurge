import { useState } from 'react'
import { Bot, X, Send } from 'lucide-react'
import { api } from '../lib/api'

export default function Assistant() {
  const [open, setOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [retry, setRetry] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [messages, setMessages] = useState<{ role: string; text: string }[]>([])
  async function ask(text: string) {
    if (!text.trim() || busy) return
    setQuestion('')
    setRetry(null)
    setMessages(m => [...m, { role: 'You', text }])
    setBusy(true)
    try {
      let status: { revision?: string }
      try {
        status = await api<{revision?: string}>('/assistant/status')
      } catch {
        throw new Error('The updated assistant backend is not available. Restart the backend, then retry.')
      }
      if (status.revision !== 'gemini-v4') {
        throw new Error('An older backend is still running. Restart the backend to load the Gemini fixes.')
      }
      const result = await api<{answer: string}>('/assistant', {
        question: text,
        history: messages.filter(m => m.role === 'You' || m.role === 'Assistant').slice(-6)
          .map(m => ({ role: m.role === 'You' ? 'user' : 'model', text: m.text.slice(0, 4000) })),
      })
      setMessages(m => [...m, { role: 'Assistant', text: result.answer }])
    } catch (e) {
      setRetry(text)
      setMessages(m => [...m, { role: 'Connection issue', text: e instanceof Error ? e.message : 'Please retry.' }])
    } finally { setBusy(false) }
  }
  return <>
    <button onClick={() => setOpen(!open)} className="fixed bottom-5 right-6 z-40 flex items-center gap-2 rounded-full bg-brand px-5 py-3 text-white shadow-xl"><Bot size={18}/> Ask datasurge</button>
    {open && <aside aria-label="Datasurge assistant" className="fixed bottom-20 right-6 z-40 flex max-h-[75vh] w-[420px] max-w-[calc(100vw-48px)] flex-col rounded-xl border border-line-strong bg-ink-900 shadow-2xl">
      <div className="flex items-center justify-between border-b border-line p-5"><div><h2 className="text-lg">Ask datasurge</h2><p className="mt-1 text-xs text-muted">Powered by Gemini · current simulation context</p></div><button aria-label="Close assistant" onClick={() => setOpen(false)}><X size={20}/></button></div>
      <div className="min-h-0 overflow-y-auto p-5" aria-live="polite">
        {!messages.length && <><p className="mb-5 text-muted">Understand your infrastructure. Explore an incident. Ask a question.</p>{['What needs my attention right now?', 'Explain how a cooling failure affects workloads.', 'What should the next shift know?'].map(q => <button key={q} onClick={() => ask(q)} className="mb-2 w-full rounded-lg border border-line p-3 text-left hover:bg-ink-800">{q}</button>)}</>}
        {messages.map((m, i) => <div key={i} className="mb-5"><p className="mb-2 text-xs text-sky">{m.role}</p><p className="whitespace-pre-wrap leading-relaxed">{m.text}</p></div>)}
        {busy && <p className="text-muted">Waiting for Gemini. Busy requests may take up to a few minutes…</p>}
        {retry && !busy && <button onClick={() => ask(retry)} className="rounded-lg border border-line px-4 py-2 text-sky">Retry question</button>}
      </div>
      <form onSubmit={e => { e.preventDefault(); ask(question) }} className="flex gap-3 border-t border-line p-4"><input aria-label="Your question" maxLength={4000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask a question…" className="min-w-0 flex-1 rounded-lg border border-line bg-ink-950 p-3"/><button aria-label="Send question" disabled={busy || !question.trim()} className="text-sky disabled:opacity-30"><Send size={20}/></button></form>
    </aside>}
  </>
}
