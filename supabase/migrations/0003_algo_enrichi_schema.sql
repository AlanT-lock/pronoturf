alter table partants add column place_corde int;
alter table courses add column allocation numeric;

create table chevaux_performances (
  id uuid primary key default gen_random_uuid(),
  cheval_id uuid not null references chevaux(id),
  date_course date not null,
  hippodrome text,
  discipline text,
  distance_m int,
  allocation numeric,
  nb_participants int,
  place int,
  status_arrivee text,
  raw_place text,
  jockey_nom text,
  poids_jockey numeric,
  corde int,
  oeillere text,
  unique (cheval_id, date_course, hippodrome, distance_m)
);
create index chevaux_performances_cheval_idx on chevaux_performances (cheval_id);
create index chevaux_performances_jockey_idx on chevaux_performances (jockey_nom);

create table entraineur_resultats (
  id uuid primary key default gen_random_uuid(),
  entraineur_nom text not null,
  cheval_id uuid not null references chevaux(id),
  date_course date not null,
  hippodrome text,
  discipline text,
  place int,
  status_arrivee text,
  unique (entraineur_nom, cheval_id, date_course)
);
create index entraineur_resultats_nom_idx on entraineur_resultats (entraineur_nom);

-- Réactivera les nouveaux poids par défaut (11 facteurs) au prochain load :
update ponderations_config set actif = false where nom = 'defaut';
