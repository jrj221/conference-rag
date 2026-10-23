-- Conference Talk RAG schema. Safe to re-run.

create extension if not exists vector;

-- One row per talk (filled by the scrape + import steps)
create table if not exists talks (
  id         bigserial primary key,
  title      text not null,
  speaker    text,
  url        text unique,
  text       text not null
);

-- One row per sentence; embedding is filled in later (step 04/05)
create table if not exists sentence_embeddings (
  id         bigserial primary key,
  talk_id    bigint not null references talks(id) on delete cascade,
  sentence   text not null,
  embedding  halfvec(1536)  -- 2 bytes/number instead of 4: half the storage, same search quality
);
create index if not exists sentence_embeddings_talk_id_idx on sentence_embeddings(talk_id);

-- Harmless public table used for the RLS contrast demo
create table if not exists page_views (
  id         bigserial primary key,
  page       text not null,
  viewed_at  timestamptz not null default now()
);

-- Semantic search: closest sentences to a query vector, with talk info.
-- Runs as the caller (security invoker), so RLS still applies.
create or replace function match_sentences(
  query_embedding vector(1536),
  match_count int default 20
)
returns table (
  sentence_id bigint,
  talk_id     bigint,
  title       text,
  speaker     text,
  sentence    text,
  similarity  float
)
language sql stable
security invoker
as $$
  select
    s.id, t.id, t.title, t.speaker, s.sentence,
    1 - (s.embedding <=> query_embedding::halfvec(1536)) as similarity
  from sentence_embeddings s
  join talks t on t.id = s.talk_id
  where s.embedding is not null
  order by s.embedding <=> query_embedding::halfvec(1536)
  limit match_count;
$$;

-- Table privileges. Newer Supabase projects don't auto-grant these to API roles.
-- GRANT = "may this role touch the table at all"; RLS below = "which rows".
grant select, insert, update, delete on talks, sentence_embeddings, page_views to service_role;
grant usage, select on all sequences in schema public to service_role;
grant select on talks, sentence_embeddings to authenticated;
grant select, insert on page_views to anon, authenticated;
grant usage on sequence page_views_id_seq to anon, authenticated;
grant execute on function match_sentences(vector, int) to authenticated, service_role;

-- Row Level Security: on everywhere. The service_role key (used by scripts) bypasses it.
alter table talks               enable row level security;
alter table sentence_embeddings enable row level security;
alter table page_views          enable row level security;

drop policy if exists "public read page_views" on page_views;
create policy "public read page_views"
  on page_views for select to anon, authenticated using (true);

-- Anyone (even logged out) may LOG a visit, but only for one of the app's tabs, so the
-- public insert can't be used to stuff arbitrary text into the table.
drop policy if exists "public log page_views" on page_views;
create policy "public log page_views"
  on page_views for insert to anon, authenticated
  with check (page in ('keyword', 'semantic', 'rag', 'history'));

drop policy if exists "authenticated read talks" on talks;
create policy "authenticated read talks"
  on talks for select to authenticated using (true);

drop policy if exists "authenticated read sentence_embeddings" on sentence_embeddings;
create policy "authenticated read sentence_embeddings"
  on sentence_embeddings for select to authenticated using (true);

-- Per-user RAG question history. Unlike the talk tables, this one is private PER USER:
-- the policies compare each row's user_id with the logged-in user's id (auth.uid()).
create table if not exists question_history (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users(id) on delete cascade,
  question    text not null,
  answer      text not null,
  sources     jsonb not null default '[]'::jsonb,  -- [{talk_id, title, speaker}, ...]
  created_at  timestamptz not null default now()
);
create index if not exists question_history_user_created_idx on question_history(user_id, created_at desc);

alter table question_history enable row level security;
grant select, insert, delete on question_history to authenticated;
grant all on question_history to service_role;

drop policy if exists "read own history" on question_history;
create policy "read own history" on question_history
  for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "add own history" on question_history;
create policy "add own history" on question_history
  for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "delete own history" on question_history;
create policy "delete own history" on question_history
  for delete to authenticated using (user_id = (select auth.uid()));
