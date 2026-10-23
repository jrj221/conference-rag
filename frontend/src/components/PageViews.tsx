import { useEffect, useState } from 'react'
import { loadRecentViews, type PageView } from '../lib/api'

// Readable by anyone, signed in or not: the public RLS policy on page_views in action
export default function PageViews({ version }: { version: number }) {
  const [data, setData] = useState<{ total: number; recent: PageView[] } | null>(null)

  useEffect(() => {
    loadRecentViews().then(setData).catch(() => setData(null))
  }, [version])

  if (!data) return null
  return (
    <footer>
      <h2>Page views ({data.total} total · public to everyone)</h2>
      <ul>
        {data.recent.map((v) => (
          <li key={v.id}>
            <strong>{v.page}</strong> — {new Date(v.viewed_at).toLocaleString()}
          </li>
        ))}
      </ul>
    </footer>
  )
}
