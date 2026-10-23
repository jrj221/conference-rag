import { useEffect, useState } from 'react'
import { deleteHistory, loadHistory, type HistoryEntry } from '../lib/api'

export default function History() {
  const [entries, setEntries] = useState<HistoryEntry[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    loadHistory().then(setEntries).catch((e) => setError(e instanceof Error ? e.message : 'Could not load history'))
  }, [])

  async function remove(id: string) {
    try {
      await deleteHistory(id)
      setEntries((prev) => prev?.filter((e) => e.id !== id) ?? null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete')
    }
  }

  if (error) return <p role="alert">{error}</p>
  if (!entries) return <p>Loading…</p>
  if (entries.length === 0) return <p>No questions yet. Ask one in the “Ask (RAG)” tab and it will appear here.</p>

  return (
    <ul className="results">
      {entries.map((e) => (
        <li key={e.id}>
          <details>
            <summary>
              <strong>{e.question}</strong>
              <small> — {new Date(e.created_at).toLocaleString()}</small>
            </summary>
            <p style={{ whiteSpace: 'pre-wrap' }}>{e.answer}</p>
            {e.sources.length > 0 && (
              <small>Sources: {e.sources.map((s) => `${s.title} (${s.speaker})`).join('; ')}</small>
            )}
            <p><button onClick={() => remove(e.id)}>Delete</button></p>
          </details>
        </li>
      ))}
    </ul>
  )
}
