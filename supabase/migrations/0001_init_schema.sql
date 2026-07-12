create table hippodromes (
  id uuid primary key default gen_random_uuid(),
  code_pmu text unique not null,
  nom text not null,
  pays text not null,
  sens_corde text
);

create table reunions (
  id uuid primary key default gen_random_uuid(),
  date date not null,
  hippodrome_id uuid not null references hippodromes(id),
  numero_reunion int not null,
  source_ids jsonb not null default '{}'::jsonb,
  unique (date, numero_reunion)
);

create table courses (
  id uuid primary key default gen_random_uuid(),
  reunion_id uuid not null references reunions(id),
  numero_course int not null,
  discipline text not null check (discipline in ('trot_attele','trot_monte','plat','obstacle')),
  distance_m int not null,
  etat_terrain text,
  categorie_classe text,
  heure_depart timestamptz not null,
  statut text not null default 'a_venir' check (statut in ('a_venir','terminee')),
  source_ids jsonb not null default '{}'::jsonb,
  unique (reunion_id, numero_course)
);

create table chevaux (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  sexe text,
  date_naissance date,
  id_pmu text unique not null,
  id_geny text
);

create table intervenants (
  id uuid primary key default gen_random_uuid(),
  nom text not null,
  role text not null check (role in ('driver','jockey','entraineur')),
  unique (nom, role)
);

create table partants (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  cheval_id uuid not null references chevaux(id),
  numero_corde int not null,
  driver_jockey_id uuid references intervenants(id),
  entraineur_id uuid references intervenants(id),
  poids_kg numeric,
  reduction_kilometrique numeric,
  ferrage text,
  musique text,
  statut text not null default 'partant' check (statut in ('partant','non_partant')),
  champs_manuels jsonb not null default '[]'::jsonb,
  unique (course_id, numero_corde)
);

create table cotes (
  id uuid primary key default gen_random_uuid(),
  partant_id uuid not null references partants(id),
  type_capture text not null check (type_capture in ('reference','direct','finale')),
  valeur numeric not null,
  capture_at timestamptz not null
);

create table resultats (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  partant_id uuid not null references partants(id) unique,
  position_arrivee int,
  disqualifie boolean not null default false,
  ecart text,
  gains numeric
);

create table ponderations_config (
  id uuid primary key default gen_random_uuid(),
  discipline text not null check (discipline in ('trot_attele','trot_monte','plat','obstacle')),
  nom text not null,
  poids jsonb not null,
  actif boolean not null default true,
  version int not null default 1,
  created_at timestamptz not null default now()
);

create table scores_pronostic (
  id uuid primary key default gen_random_uuid(),
  course_id uuid not null references courses(id),
  partant_id uuid not null references partants(id),
  ponderation_config_id uuid not null references ponderations_config(id),
  score_total numeric not null,
  rang_pronostique int not null,
  details_facteurs jsonb not null default '{}'::jsonb,
  calculated_at timestamptz not null default now()
);

create table backtest_resultats (
  id uuid primary key default gen_random_uuid(),
  ponderation_config_id uuid not null references ponderations_config(id),
  periode_debut date not null,
  periode_fin date not null,
  nb_courses int not null,
  precision_top1 numeric,
  precision_top3 numeric,
  calculated_at timestamptz not null default now()
);
