import { useState } from 'react'
import { askQuestion, saveHistory, type Talk, explainError } from '../lib/api'

export default function Search() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [answer, setAnswer] = useState('')
  const [talks, setTalks] = useState<Talk[]>([])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const result = await askQuestion(question)
      setAnswer(result.answer)
      setTalks(result.talks)
      // A failed save shouldn't hide an answer the user already has
      saveHistory(question, result.answer, result.talks).catch((e) => console.error('Could not save history', e))
    } catch (err) {
      setError(explainError(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <form onSubmit={onSubmit}>
        <input value={question} placeholder="Ask about General Conference talks…"
          onChange={(e) => setQuestion(e.target.value)} />
        <button type="submit" disabled={loading || !question.trim()}>
          {loading ? 'Thinking…' : 'Ask'}
        </button>
      </form>
      {error && <p role="alert">{error}</p>}
      {answer && (
        <section>
          <h2>Answer</h2>
          <p style={{ whiteSpace: 'pre-wrap' }}>{answer}</p>
        </section>
      )}
      {talks.length > 0 && (
        <section>
          <h2>Sources</h2>
          <ul>
            {talks.map((t) => (
              <li key={t.talk_id}>
                <strong>{t.title}</strong> — {t.speaker}
                {t.similarity !== undefined && ` (${t.similarity.toFixed(3)})`}
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  )
}
