import { useEffect, useState } from 'react'
import type { Session } from '@supabase/supabase-js'
import { supabase } from './lib/supabase'
import Login from './components/Login'
import Search from './components/Search'
import KeywordSearch from './components/KeywordSearch'
import SemanticSearch from './components/SemanticSearch'
import History from './components/History'

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

  if (!ready) return null

  return (
    <main>
      <h1>Conference Talk RAG</h1>
      {session ? (
        <>
          <p>
            Signed in as {session.user.email}{' '}
            <button onClick={() => supabase.auth.signOut()}>Sign out</button>
          </p>
          <nav className="tabs">
            {MODES.map((m) => (
              <button key={m.id} aria-pressed={mode === m.id}
                onClick={() => setMode(m.id)}>{m.label}</button>
            ))}
          </nav>
          {mode === 'keyword' && <KeywordSearch />}
          {mode === 'semantic' && <SemanticSearch />}
          {mode === 'rag' && <Search />}
          {mode === 'history' && <History />}
        </>
      ) : (
        <Login />
      )}
    </main>
  )
}
