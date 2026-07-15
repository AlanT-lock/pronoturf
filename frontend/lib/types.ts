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

export type ProgrammeCourse = {
  numero_course: number;
  discipline: string | null;
  distance_m: number | null;
  heure_depart: string | null;
  statut: string;
  nombre_partants: number | null;
  allocation: number | null;
  paris: string[];
  est_quinte: boolean;
};

export type ProgrammeReunion = {
  numero_reunion: number;
  hippodrome: string;
  pays: string;
  courses: ProgrammeCourse[];
};

export type Programme = { date: string; reunions: ProgrammeReunion[] };

export type Recommandation = {
  type_pari: string;
  selection: number[];
  base: number[];
  tournant: number[];
  confiance: number;
  niveau: string;
  avis: string;
};

export type CoupDeCoeur = { numero_corde: number; raison: string };

export type AnalyseIA = {
  id: string;
  course_id: string;
  modele: string;
  source: string;
  lecture_globale: string | null;
  recommandations: Recommandation[];
  coup_de_coeur_value: CoupDeCoeur | null;
  confiance_globale: number | null;
  created_at?: string;
};

export type CalibrationBin = {
  bucket: string;
  n: number;
  confiance_moyenne: number;
  taux_top1_reel: number;
};

export type Backtest = {
  nb_courses: number;
  precision_top1: number | null;
  precision_top3: number | null;
  brier_confiance: number | null;
  calibration: CalibrationBin[];
  calibration_gate: { disponible: boolean; nb_paires: number; seuil: number };
};
