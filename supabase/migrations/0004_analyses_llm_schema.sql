-- Analyse IA par course (une analyse « courante » par course).
create table analyses_llm (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  modele text not null,
  source text not null default 'llm',          -- 'llm' | 'regles' (repli déterministe)
  recommandations jsonb not null default '[]'::jsonb,
  lecture_globale text,
  coup_de_coeur_value jsonb,                    -- { numero_corde, raison } | null
  input_snapshot jsonb,                         -- signaux envoyés + paris (audit & DATA)
  confiance_globale numeric,
  created_at timestamptz not null default now(),
  unique (course_id)
);
create index analyses_llm_course_idx on analyses_llm (course_id);

-- Table jumelle : conserve la DATA longitudinale lors d'une ré-analyse (force=true).
create table analyses_llm_historique (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  modele text not null,
  source text,
  recommandations jsonb,
  lecture_globale text,
  coup_de_coeur_value jsonb,
  input_snapshot jsonb,
  confiance_globale numeric,
  created_at timestamptz,
  archived_at timestamptz not null default now()
);
create index analyses_llm_historique_course_idx on analyses_llm_historique (course_id);
