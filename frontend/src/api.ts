export type User = {
  id: string;
  email: string;
  full_name: string;
  preferred_language: "en" | "ta";
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
  value: number;
  shap_importance: number;
  effect: string;
};

export type RiskResult = {
  status: string;
  overall_risk_score: number;
  risk_category: "low" | "moderate" | "high";
  disease_conduciveness_scores: {
    red_rot: number;
    rust: number;
    wilt: number;
  };
  forecast_lead_time: string;
  processing_time_ms: number;
  primary_drivers: RiskDriver[];
  weather_summary: {
    temperature_mean_7d: number;
    temperature_min_7d: number;
    relative_humidity_7d: number;
    precipitation_sum_7d: number;
    thi_index: number;
  };
  scientific_disclosure: string;
  id?: string;
  saved_to_history?: boolean;
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
