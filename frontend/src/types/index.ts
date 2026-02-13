/* TypeScript Interfaces fuer Planung SBP */

export interface User {
  id: number;
  email?: string;
  role: "admin" | "musiker";
}

export interface AuthState {
  token: string | null;
  user: User | null;
  isAuthenticated: boolean;
}

export interface Season {
  id: number;
  name: string;
  start_date: string;
  end_date: string;
  is_active: boolean;
  event_count: number;
  project_count: number;
}

export type EventStatus = "fest" | "geplant" | "moeglich";

export interface SBPEvent {
  id: number;
  project_id: number | null;
  season_id: number;
  event_date: string;
  start_time: string | null;
  end_time: string | null;
  dienst_type: string;
  formation: string;
  status: EventStatus;
  programm: string;
  ort: string;
  ort_adresse: string;
  leitung: string;
  kleidung: string;
  sonstiges: string;
  raw_text: string;
  project_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: number;
  season_id: number;
  name: string;
  description: string;
  status: EventStatus;
  formation: string | null;
  conductor: string | null;
  soloist: string | null;
  moderator: string | null;
  notes: string | null;
  event_count: number;
  events?: SBPEvent[];
  created_at: string;
  updated_at: string;
}

export interface Musician {
  id: number;
  name: string;
  position: string;
  register: string;
  gruppe: string;
  anteil: number;
  zusatz: string;
  is_vakant: boolean;
  display_name: string;
  ensembles: string[];
}

export interface GeneratedPlan {
  id: number;
  season_id: number | null;
  plan_start: string;
  plan_end: string;
  status: string;
  has_collective_docx: boolean;
  has_collective_pdf: boolean;
  individual_count: number;
  created_at: string;
  individual_plans?: IndividualPlanSummary[];
}

export interface IndividualPlanSummary {
  id: number;
  display_name: string;
  is_vakant: boolean;
  has_docx: boolean;
  has_pdf: boolean;
}

export interface Violation {
  rule_id: string;
  rule_name: string;
  severity: "ERROR" | "WARNING" | "INFO";
  message: string;
  tvk_paragraph: string;
  affected_dates: string[];
  affected_week: number | null;
  current_value: number | null;
  limit_value: number | null;
  suggestion: string;
}

export interface ValidationResult {
  status: "ok" | "warning" | "error";
  week_start: string;
  week_end: string;
  total_dienste: number;
  max_dienste: number;
  violations: Violation[];
  summary: Record<string, number>;
}

/* Dienst-Typen und Formationen als konstante Arrays */
export const DIENST_TYPES = [
  "Probe", "GP", "HP", "Anspielprobe", "Konzert", "Abo-Konzert",
  "SK", "Babykonzert", "Dirigierkurs", "Podcast", "Gastspiel",
  "Reise", "RZA", "Dienstberatung", "Probespiel", "Tonaufnahme",
  "Akademiedienst", "Frei", "Urlaub", "Sonstiges",
] as const;

export const FORMATIONS = [
  "SBP", "Brass inkl. Schlagz.", "Brass ohne Schlagz.", "BLQ", "KLQ",
  "SBQ", "Serenaden", "Holz", "Blech", "Schlagwerk", "Kontrabass",
  "Gremien", "Strategierat", "Gruppen", "Unbekannt",
] as const;

export const STATUS_OPTIONS: EventStatus[] = ["fest", "geplant", "moeglich"];

/* Farb-Mapping fuer Formationen */
export const FORMATION_COLORS: Record<string, string> = {
  "SBP": "#0071E3",
  "Brass inkl. Schlagz.": "#FF9F0A",
  "Brass ohne Schlagz.": "#FF9F0A",
  "BLQ": "#34C759",
  "KLQ": "#5856D6",
  "SBQ": "#FF2D55",
  "Serenaden": "#AF52DE",
  "Holz": "#00C7BE",
  "Blech": "#FF9F0A",
  "Schlagwerk": "#FF6B35",
  "Kontrabass": "#8E8E93",
};

export const STATUS_COLORS: Record<EventStatus, string> = {
  fest: "#1D1D1F",
  geplant: "#6E6E73",
  moeglich: "#AEAEB2",
};

/* Farb-Mapping fuer Dienst-Typen (Kalender-Dots) */
export const DIENST_TYPE_COLORS: Record<string, string> = {
  "Konzert": "#0071E3",
  "Abo-Konzert": "#0071E3",
  "SK": "#5856D6",
  "Babykonzert": "#AF52DE",
  "Gastspiel": "#007AFF",
  "Probe": "#34C759",
  "GP": "#30D158",
  "HP": "#34C759",
  "Anspielprobe": "#63E6BE",
  "Dirigierkurs": "#FF9F0A",
  "Podcast": "#FF6B35",
  "Tonaufnahme": "#FF6B35",
  "Akademiedienst": "#FF9F0A",
  "Reise": "#8E8E93",
  "RZA": "#8E8E93",
  "Urlaub": "#AEAEB2",
  "Frei": "#AEAEB2",
  "Dienstberatung": "#6E6E73",
  "Probespiel": "#FF2D55",
  "Sonstiges": "#6E6E73",
};
