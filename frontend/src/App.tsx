import { useEffect, useRef, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import { logPageView } from './lib/api'
import Login from './components/Login'
import Search from './components/Search'
import KeywordSearch from './components/KeywordSearch'
import SemanticSearch from './components/SemanticSearch'
import History from './components/History'
import PageViews from './components/PageViews'

const MODES = [
  { id: 'keyword', label: 'Keyword' },
  { id: 'semantic', label: 'Semantic' },
  { id: 'rag', label: 'Ask (RAG)' },
  { id: 'history', label: 'History' },
] as const
type Mode = (typeof MODES)[number]['id']

export default function App() {
  const [session, setSession] = useState<Session | null>(null)
  const [ready, setReady] = useState(false)
  const [mode, setMode] = useState<Mode>('keyword')
  const [viewsVersion, setViewsVersion] = useState(0)
  const lastLogged = useRef<Mode | null>(null)

  useEffect(() => {
    // Never leave the page blank if the session check fails or hangs (e.g. unreachable backend)
    const fallback = setTimeout(() => setReady(true), 4000)
    supabase.auth.getSession()
      .then(({ data }) => setSession(data.session))
      .catch(() => setSession(null))
      .finally(() => {
        clearTimeout(fallback)
        setReady(true)
      })
    const { data: sub } = supabase.auth.onAuthStateChange((_event, s) => setSession(s))
    return () => sub.subscription.unsubscribe()
  }, [])

  // Each tab is a "page": log a view (time is stamped by the database) when it is opened.
  // Works for visitors who are not signed in, because page_views allows anonymous inserts.
  useEffect(() => {
    if (!ready || lastLogged.current === mode) return
    lastLogged.current = mode
    logPageView(mode)
      .then(() => setViewsVersion((v) => v + 1))
      .catch((e) => console.error('Could not log page view', e))
  }, [mode, ready])

  if (!ready) return null

  return (
    <main>
      <h1>Conference Talk RAG</h1>
      {session ? (
        <p>
          Signed in as {session.user.email}{' '}
          <button onClick={() => supabase.auth.signOut()}>Sign out</button>
        </p>
      ) : (
        <>
          <p>You're browsing as a visitor. Page views are public, but searching and history need an account.</p>
          <Login />
        </>
      )}
      <nav className="tabs">
        {MODES.map((m) => (
          <button key={m.id} aria-pressed={mode === m.id} onClick={() => setMode(m.id)}>{m.label}</button>
        ))}
      </nav>
      {/* key={session id} remounts the tab after sign-in/out so stale errors and results clear */}
      <div key={session?.user.id ?? 'visitor'}>
        {mode === 'keyword' && <KeywordSearch />}
        {mode === 'semantic' && <SemanticSearch />}
        {mode === 'rag' && <Search />}
        {mode === 'history' && <History />}
      </div>
      <PageViews version={viewsVersion} />
    </main>
  )
}
