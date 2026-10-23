import { useState } from 'react'
import { semanticSearch, type SentenceHit, explainError } from '../lib/api'

export default function SemanticSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SentenceHit[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      setResults(await semanticSearch(query))
    } catch (err) {
      setError(explainError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <form onSubmit={onSubmit}>
        <input value={query} placeholder="Describe an idea, e.g. finding comfort after loss"
          onChange={(e) => setQuery(e.target.value)} />
        <button type="submit" disabled={loading || !query.trim()}>{loading ? 'Searching…' : 'Search'}</button>
      </form>
      {error && <p role="alert">{error}</p>}
      <ul className="results">
        {results.map((r) => (
          <li key={r.sentence_id}>
            <p>{r.sentence}</p>
            <small>{r.title} — {r.speaker} · similarity {r.similarity.toFixed(3)}</small>
          </li>
        ))}
      </ul>
    </>
  )
}
