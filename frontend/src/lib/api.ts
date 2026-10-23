import { supabase } from './supabase'

export interface Talk {
  talk_id: number
  title: string
  speaker: string
  text: string
  similarity?: number
}

// Edge Functions verify the JWT manually (deployed with --no-verify-jwt),
// so we must send the logged-in user's access token.
async function callFunction<T>(name: string, body: Record<string, unknown>): Promise<T> {
  const { data, error } = await supabase.functions.invoke(name, { body })
  if (error) throw error
  return data as T
}

// Step 05: question -> 1,536-dim vector (OpenAI key stays server-side)
export async function embedQuestion(question: string): Promise<number[]> {
  const { embedding } = await callFunction<{ embedding: number[] }>('embed-question', { question })
  return embedding
}

export interface SentenceHit {
  sentence_id: number
  talk_id: number
  title: string
  speaker: string
  sentence: string
  similarity: number
}

// Retrieve: nearest sentences -> the best talks, ranked by their strongest matching sentence.
// Then fetch those talks' FULL text, so GPT has surrounding context, not just isolated sentences.
export async function matchTalks(embedding: number[], topTalks = 5): Promise<Talk[]> {
  const { data, error } = await supabase.rpc('match_sentences', {
    query_embedding: embedding,
    match_count: 40,
  })
  if (error) throw error

  const best = new Map<number, SentenceHit>() // hits arrive best-first, so the first hit per talk is its best
  for (const hit of data as SentenceHit[]) if (!best.has(hit.talk_id)) best.set(hit.talk_id, hit)
  const ranked = [...best.values()].slice(0, topTalks)

  const { data: talks, error: talksError } = await supabase
    .from('talks')
    .select('id, text')
    .in('id', ranked.map((h) => h.talk_id))
  if (talksError) throw talksError
  const textById = new Map((talks ?? []).map((t) => [t.id as number, t.text as string]))

  return ranked.map((h) => ({
    talk_id: h.talk_id,
    title: h.title,
    speaker: h.speaker,
    text: textById.get(h.talk_id) ?? h.sentence,
    similarity: h.similarity,
  }))
}

// Step 06: GPT-4o answers using the retrieved talks as context
export async function generateAnswer(question: string, contextTalks: Talk[]): Promise<string> {
  const { answer } = await callFunction<{ answer: string }>('generate-answer', {
    question,
    context_talks: contextTalks.map(({ title, speaker, text }) => ({ title, speaker, text })),
  })
  return answer
}

// Full RAG pipeline: retrieve -> augment -> generate
export async function askQuestion(question: string) {
  const embedding = await embedQuestion(question)
  const talks = await matchTalks(embedding)
  const answer = await generateAnswer(question, talks)
  return { answer, talks }
}

export interface SentenceResult {
  id: number
  sentence: string
  talks: { title: string; speaker: string; url: string } | null
}

// Escape LIKE wildcards so a user typing "50%" or "a_b" searches for those literal characters
const escapeLike = (s: string) => s.replace(/[\\%_]/g, (c) => '\\' + c)

// Keyword search: every word must appear in the sentence (case-insensitive substring match).
// No embeddings involved, so "peace" will NOT find "comfort" or "solace".
export async function keywordSearch(query: string, limit = 50): Promise<SentenceResult[]> {
  const words = query.split(/\s+/).filter(Boolean)
  let q = supabase.from('sentence_embeddings').select('id, sentence, talks(title, speaker, url)')
  for (const w of words) q = q.ilike('sentence', `%${escapeLike(w)}%`)
  const { data, error } = await q.limit(limit)
  if (error) throw error
  return data as unknown as SentenceResult[]
}

// Semantic search: embed the question, then return the closest sentences by meaning.
// Needs the embed-question Edge Function deployed and embeddings loaded in the database.
export async function semanticSearch(query: string, limit = 20): Promise<SentenceHit[]> {
  const embedding = await embedQuestion(query)
  const { data, error } = await supabase.rpc('match_sentences', {
    query_embedding: embedding,
    match_count: limit,
  })
  if (error) throw error
  return data as SentenceHit[]
}

export interface HistoryEntry {
  id: string
  question: string
  answer: string
  sources: { talk_id: number; title: string; speaker: string }[]
  created_at: string
}

// user_id is filled in by the database (default auth.uid()), and RLS rejects anything not ours
export async function saveHistory(question: string, answer: string, talks: Talk[]) {
  const sources = talks.map(({ talk_id, title, speaker }) => ({ talk_id, title, speaker }))
  const { error } = await supabase.from('question_history').insert({ question, answer, sources })
  if (error) throw error
}

// No user filter needed: RLS only ever returns the logged-in user's rows
export async function loadHistory(): Promise<HistoryEntry[]> {
  const { data, error } = await supabase
    .from('question_history')
    .select('id, question, answer, sources, created_at')
    .order('created_at', { ascending: false })
    .limit(100)
  if (error) throw error
  return data as HistoryEntry[]
}

export async function deleteHistory(id: string) {
  const { error } = await supabase.from('question_history').delete().eq('id', id)
  if (error) throw error
}

// ---- Page view logging: public on purpose (anon can insert/read page_views) ----
export type PageName = 'keyword' | 'semantic' | 'rag' | 'history'

export async function logPageView(page: PageName) {
  const { error } = await supabase.from('page_views').insert({ page })
  if (error) throw error
}

export interface PageView {
  id: number
  page: string
  viewed_at: string
}

export async function loadRecentViews(limit = 8): Promise<{ total: number; recent: PageView[] }> {
  const { data, count, error } = await supabase
    .from('page_views')
    .select('id, page, viewed_at', { count: 'exact' })
    .order('viewed_at', { ascending: false })
    .limit(limit)
  if (error) throw error
  return { total: count ?? 0, recent: data as PageView[] }
}

// Turns "permission denied" / 401 failures (what RLS and grants produce for visitors who
// aren't signed in) into an explanation, and keeps the raw error visible for learning.
export function explainError(err: unknown): string {
  const e = err as { message?: string; code?: string; context?: { status?: number } }
  const raw = e?.message ?? 'Something went wrong'
  const denied = e?.code === '42501' || e?.context?.status === 401 || /permission denied/i.test(raw)
  return denied
    ? `Sign in required. The server rejected this request because visitors who aren't signed in have no access to it. (${raw})`
    : raw
}
