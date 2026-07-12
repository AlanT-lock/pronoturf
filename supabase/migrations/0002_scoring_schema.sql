-- Dédoublonnage éventuel des cotes avant d'ajouter la contrainte unique :
-- garde la ligne la plus récente par (partant_id, type_capture).
delete from cotes c
using cotes c2
where c.partant_id = c2.partant_id
  and c.type_capture = c2.type_capture
  and c.capture_at < c2.capture_at;

alter table cotes
  add constraint cotes_partant_type_unique unique (partant_id, type_capture);

alter table partants
  add column age int,
  add column nombre_courses int,
  add column nombre_victoires int,
  add column nombre_places int,
  add column gains_carriere numeric,
  add column gains_annee_en_cours numeric;
