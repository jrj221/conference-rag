import { corsHeaders, json } from '../_shared/cors.ts'
import { getUser } from '../_shared/auth.ts'

const MAX_QUESTION_CHARS = 1000

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })
  if (req.method !== 'POST') return json({ error: 'Use POST' }, 405)

  // 1. Only logged-in users may spend our OpenAI credit
  if (!(await getUser(req))) return json({ error: 'Unauthorized' }, 401)

  // 2. Validate input
  let question: unknown
  try {
    ;({ question } = await req.json())
  } catch {
    return json({ error: 'Body must be JSON: { "question": "..." }' }, 400)
  }
  if (typeof question !== 'string' || !question.trim() || question.length > MAX_QUESTION_CHARS) {
    return json({ error: `"question" must be a non-empty string under ${MAX_QUESTION_CHARS} characters` }, 400)
  }

  // 3. Ask OpenAI for the embedding. The key lives in a Supabase secret, never in the browser.
  const resp = await fetch('https://api.openai.com/v1/embeddings', {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${Deno.env.get('OPENAI_API_KEY')}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ model: 'text-embedding-3-small', input: question.trim() }),
  })
  if (!resp.ok) {
    console.error('OpenAI error', resp.status, await resp.text())
    return json({ error: 'Embedding service failed' }, 502)
  }

  const { data } = await resp.json()
  return json({ embedding: data[0].embedding })
})
