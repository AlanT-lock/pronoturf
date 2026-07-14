const LABELS: Record<string, string> = {
  SIMPLE_GAGNANT: "Simple Gagnant", SIMPLE_PLACE: "Simple Placé",
  COUPLE_GAGNANT: "Couplé Gagnant", COUPLE_PLACE: "Couplé Placé",
  COUPLE_ORDRE: "Couplé Ordre", DEUX_SUR_QUATRE: "2 sur 4",
  TRIO: "Trio", TRIO_ORDRE: "Trio Ordre", TIERCE: "Tiercé",
  QUARTE_PLUS: "Quarté+", QUINTE_PLUS: "Quinté+", MULTI: "Multi",
  MINI_MULTI: "Mini Multi", SUPER_QUATRE: "Super Quatre",
  PICK5: "Pick 5", REPORT_PLUS: "Report+",
};

export function libellePari(code: string): string {
  return LABELS[code] ?? code;
}
