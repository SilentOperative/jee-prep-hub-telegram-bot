-- Standalone Telegram bot schema for JEE Prep Hub.
-- Review this file before applying it to your Supabase project.
-- Bot operations use the service-role key only on the private Python worker.
-- RLS is enabled as defense in depth; do not grant public table access.

create extension if not exists pgcrypto;

create table if not exists public.bot_profiles (
  telegram_id bigint primary key,
  display_name text not null default 'Student',
  username text,
  xp integer not null default 0 check (xp >= 0),
  level integer not null default 1 check (level >= 1),
  streak integer not null default 0 check (streak >= 0),
  last_active date,
  created_at timestamptz not null default now()
);

create table if not exists public.daily_missions (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null references public.bot_profiles(telegram_id) on delete cascade,
  mission_date date not null,
  title text not null,
  description text not null,
  xp_reward integer not null default 10 check (xp_reward between 0 and 100),
  completed boolean not null default false,
  created_at timestamptz not null default now(),
  unique (telegram_id, mission_date)
);

create table if not exists public.quiz_questions (
  id uuid primary key default gen_random_uuid(),
  subject text not null check (subject in ('Physics','Chemistry','Mathematics','Biology','General')),
  topic text not null,
  difficulty text not null default 'medium' check (difficulty in ('easy','medium','hard')),
  question text not null,
  options jsonb not null check (jsonb_typeof(options) = 'array' and jsonb_array_length(options) = 4),
  correct_index integer not null check (correct_index between 0 and 3),
  explanation text not null default '',
  source_url text,
  is_active boolean not null default true,
  created_at timestamptz not null default now()
);

create table if not exists public.quiz_attempts (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null references public.bot_profiles(telegram_id) on delete cascade,
  question_id uuid not null references public.quiz_questions(id) on delete cascade,
  chosen_index integer not null check (chosen_index between 0 and 3),
  correct boolean not null,
  subject text not null,
  topic text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.mistake_memory (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null references public.bot_profiles(telegram_id) on delete cascade,
  question_id uuid references public.quiz_questions(id) on delete set null,
  subject text not null,
  topic text not null,
  question_snapshot text not null,
  explanation_snapshot text not null default '',
  reviewed boolean not null default false,
  created_at timestamptz not null default now(),
  reviewed_at timestamptz
);

create table if not exists public.backlog_tasks (
  id uuid primary key default gen_random_uuid(),
  telegram_id bigint not null references public.bot_profiles(telegram_id) on delete cascade,
  title text not null,
  status text not null default 'open' check (status in ('open','done','paused')),
  priority text not null default 'normal' check (priority in ('low','normal','high')),
  created_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists public.resource_links (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  subject text not null,
  topic text not null,
  url text not null check (url ~ '^https?://'),
  description text not null default '',
  is_published boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_attempts_user_time on public.quiz_attempts(telegram_id, created_at desc);
create index if not exists idx_mistakes_user_reviewed on public.mistake_memory(telegram_id, reviewed, created_at desc);
create index if not exists idx_backlog_user_status on public.backlog_tasks(telegram_id, status);
create index if not exists idx_questions_subject_topic on public.quiz_questions(subject, topic) where is_active;

alter table public.bot_profiles enable row level security;
alter table public.daily_missions enable row level security;
alter table public.quiz_questions enable row level security;
alter table public.quiz_attempts enable row level security;
alter table public.mistake_memory enable row level security;
alter table public.backlog_tasks enable row level security;
alter table public.resource_links enable row level security;

-- No anon/authenticated policies are intentionally created. The private bot worker
-- uses its server-side service-role key. Never expose that key to users or clients.
