import type { Language } from "./i18n";

export type User = {
  id: string;
  email: string;
  full_name: string;
  preferred_language: Language;
  role: string;
};

export type DiagnosisHistory = {
  id: string;
  predicted_class: string | null;
  confidence: number | null;
  status: string;
  detector_model_version: string | null;
  classifier_model_version: string | null;
  created_at: string;
};

export type RiskHistory = {
  id: string;
  disease_class: string;
  risk_score: number | null;
  risk_category: string | null;
  status: string;
  created_at: string;
};

export type Knowledge = {
  disease_class: string;
  language_code: "en" | "ta";
  display_name: string;
  scientific_name: string | null;
  symptoms: string;
  preventive_guidance: string;
  monitoring_guidance: string;
  management_guidance: string | null;
  source_reference: string;
  last_reviewed_at: string | null;
};

export type ModelVersion = {
  id: string;
  model_type: string;
  version: string;
  artifact_reference: string | null;
  framework: string | null;
  dataset_version: string | null;
  is_active: boolean;
  created_at: string;
};

export type Farm = {
  id: string;
  name: string;
  latitude: number | null;
  longitude: number | null;
  soil_ph: number | null;
  crop_variety: string | null;
  planting_date: string | null;
  growth_stage: string | null;
  created_at: string;
};

export type ImageQuality = {
  is_acceptable: boolean;
  blur_score: number;
  is_blurry: boolean;
  brightness_score: number;
  lighting: "optimal" | "dark" | "glare";
  contrast_score: number;
  resolution: string;
  quality_warnings: string[];
};

export type UncertaintyInfo = {
  is_uncertain: boolean;
  predictive_entropy: number;
  margin_to_second: number;
  confidence_level: "high" | "moderate" | "low / uncertain";
  reason: string | null;
};

export type DiagnosisResult = {
  status: string;
  predicted_class: string;
  uncalibrated_score: number;
  alternative_predictions: { disease_class: string; uncalibrated_score: number }[];
  model_version: string;
  processing_time_ms: number;
  warning: string;
  saved_to_history: boolean;
  explanation?: string | null;
  heatmap_base64?: string | null;
  image_quality?: ImageQuality;
  uncertainty?: UncertaintyInfo;
};

export type RiskDriver = {
  feature: string;
  value: number | null;
  shap_value: number;
  effect: string;
};

export type RiskResult = {
  status: string;
  disease_class: string;
  disease_presence_score: number;
  score_note: string;
  processing_time_ms: number;
  primary_drivers: RiskDriver[];
  input_features: Record<string, number | null>;
  model_version: string;
  scientific_disclosure: string;
  id?: string;
  saved_to_history?: boolean;
};

export type DiseaseObservationReport = {
  id: string;
  farm_id: string | null;
  disease_class: string;
  reported_outcome: "symptoms_seen" | "not_seen" | "unsure";
  outcome: "present" | "absent" | null;
  verification_status: "pending" | "verified";
  observation_date: string;
  research_consent: boolean;
  created_at?: string;
};

export type PendingDiseaseObservation = {
  id: string;
  farm_id: string | null;
  reported_by_user_id: string | null;
  disease_class: string;
  reported_outcome: "symptoms_seen" | "not_seen" | "unsure";
  observation_date: string;
  environment_snapshot: {
    soil_ph: number | null;
    weather: {
      temperature_c: number | null;
      relative_humidity_pct: number | null;
      rainfall_mm: number | null;
      wind_speed_kmh: number | null;
      dew_point_c: number | null;
      source: string;
      freshness: string;
    } | null;
  } | null;
  research_consent: boolean;
  notes: string | null;
  created_at: string;
};

export type WeatherObservation = {
  status: "available" | "stale" | "unavailable";
  provider: string;
  cached: boolean;
  timestamp: string | null;
  observation?: {
    temperature_mean: number | null;
    relative_humidity: number | null;
    dew_point: number | null;
    precipitation: number | null;
    wind_speed: number | null;
  };
  message?: string | null;
};

export type WeatherGuidance = {
  status: "generated";
  model: string;
  weather_observed_at: string;
  weather_freshness: "current" | "cached";
  weather_history_days: number;
  weather_measurements: {
    temperature_c: number | null;
    relative_humidity_pct: number | null;
    dew_point_c: number | null;
    rainfall_mm: number | null;
    wind_speed_kmh: number | null;
  };
  disease_class: string;
  risk_level: "insufficient_data" | "low" | "moderate" | "high";
  risk_reason: string;
  summary: string;
  weather_effect: string;
  actions: string[];
  watch_for: string[];
  limitations: string;
};

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000/api/v1";

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    throw new Error(typeof detail === "string" ? detail : detail?.message ?? "The request could not be completed.");
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function downloadVerifiedTrainingData(): Promise<void> {
  const response = await fetch(`${API_BASE}/admin/disease-observations/training.csv`, {
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : "Verified training data could not be downloaded.");
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "verified-environmental-observations.csv";
  link.click();
  URL.revokeObjectURL(url);
}
