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
