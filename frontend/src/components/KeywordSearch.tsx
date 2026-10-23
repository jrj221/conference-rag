import { useState } from 'react'
import { keywordSearch, type SentenceResult } from '../lib/api'

// Wrap each search word in <mark> so you can see WHY a sentence matched
function highlight(text: string, words: string[]) {
  if (!words.length) return text
  const pattern = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|')})`, 'gi')
  return text.split(pattern).map((part, i) =>
    i % 2 === 1 ? <mark key={i}>{part}</mark> : part,
  )
}

export default function KeywordSearch() {
  const [query, setQuery] = useState('')
  const [searched, setSearched] = useState('')
  const [results, setResults] = useState<SentenceResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      setResults(await keywordSearch(query))
      setSearched(query)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed')
    } finally {
      setLoading(false)
    }
  }

  const words = searched.split(/\s+/).filter(Boolean)

  return (
    <>
      <form onSubmit={onSubmit}>
        <input value={query} placeholder="Keywords, e.g. peace comfort" onChange={(e) => setQuery(e.target.value)} />
        <button type="submit" disabled={loading || !query.trim()}>{loading ? 'Searching…' : 'Search'}</button>
      </form>
      {error && <p role="alert">{error}</p>}
      {searched && !loading && !error && (
        <p>{results.length === 50 ? '50+' : results.length} sentence(s) containing all of: {words.join(', ')}</p>
      )}
      <ul className="results">
        {results.map((r) => (
          <li key={r.id}>
            <p>{highlight(r.sentence, words)}</p>
            {r.talks && (
              <small>
                <a href={r.talks.url} target="_blank" rel="noreferrer">{r.talks.title}</a> — {r.talks.speaker}
              </small>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}
