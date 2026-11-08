import Assistant from './components/Assistant'
import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useLive } from './lib/api'
import { AppProvider, useApp } from './lib/ctx'
import { SideNav, Toasts, TopBar } from './components/Shell'
import IncidentDrawer from './components/IncidentDrawer'
import ConsolePage from './pages/ConsolePage'
import { HandoffPage, IncidentsPage, MigrationsPage, MyViewPage, OnCallPage } from './pages/OtherPages'

function Layout({ connected }: { connected: boolean }) {
  const { page, openIncident } = useApp()
  const [collapsed, setCollapsed] = useState(false)
  return (
    <div className="flex h-full flex-col">
      <TopBar connected={connected} onToggleNav={() => setCollapsed(!collapsed)} />
      <div className="flex min-h-0 flex-1">
        <SideNav collapsed={collapsed} />
        <main className="min-w-0 flex-1 overflow-hidden bg-ink-950">
          {page === 'console' && <ConsolePage />}
          {page === 'incidents' && <IncidentsPage />}
          {page === 'migrations' && <MigrationsPage />}
          {page === 'handoff' && <HandoffPage />}
          {page === 'oncall' && <OnCallPage />}
          {page === 'myview' && <MyViewPage />}
        </main>
      </div>
      {openIncident && <IncidentDrawer />}
      <Assistant />
      <Toasts />
    </div>
  )
}

export default function App() {
  const { state, topology, connected } = useLive()
  if (!state || !topology) {
    return (
      <div className="grid h-full place-items-center">
        <div className="flex items-center gap-3 text-muted">
          <Loader2 className="animate-spin text-brand-hi" size={20} />
          Connecting to datasurge backend… <span className="text-faint">(start it with <code className="text-sky">./run.sh</code>)</span>
        </div>
      </div>
    )
  }
  return (
    <AppProvider state={state} topology={topology}>
      <Layout connected={connected} />
    </AppProvider>
  )
}
