export type FactorDetail = { valeur: number; poids_effectif: number; contribution: number };

export type Partant = {
  partant_id: string;
  numero_corde: number;
  nom_cheval: string;
  sexe: string | null;
  age: number | null;
  musique: string | null;
  nombre_courses: number | null;
  nombre_victoires: number | null;
  nombre_places: number | null;
  poids_kg: number | null;
  reduction_kilometrique: number | null;
  ferrage: string | null;
  statut: string;
  cote_retenue: number | null;
  jockey_nom: string | null;
  entraineur_nom: string | null;
};

export type Course = {
  id: string;
  numero_course: number;
  discipline: string;
  distance_m: number;
  statut: string;
  etat_terrain: string | null;
};

export type ScoreRow = {
  partant_id: string;
  numero_corde: number;
  nom_cheval: string;
  score_total: number;
  rang: number;
  details_facteurs: Record<string, FactorDetail>;
  cote?: number | null;
  confiance?: number;
  nb_courses_historique?: number;
};
