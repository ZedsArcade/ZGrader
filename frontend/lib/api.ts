// Typed client for the ZGrader backend, reached via the same-origin /api/*
// rewrite configured in next.config.ts (see that file for why).

const API_BASE = "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export type UserRole = "client" | "operator";

export interface User {
  id: string;
  email: string;
  is_verified: boolean;
  role: UserRole;
}

export interface Card {
  game: string;
  card_name: string;
  set_name: string | null;
  card_number: string | null;
  foil: boolean;
}

export type SubmissionStatus =
  | "created"
  | "awaiting_scans"
  | "processing"
  | "draft_ready"
  | "approved"
  | "published"
  | "error";

export interface SubmissionSummary {
  submission_code: string;
  status: SubmissionStatus;
  created_at: string;
}

export interface AnalysisResult {
  category: string;
  side: "front" | "back" | "combined";
  raw_score: number;
  measurements: Record<string, unknown>;
  flags: Record<string, unknown>;
}

export interface Comparison {
  company: "PSA" | "BGS" | "CGC" | "TAG";
  category: string;
  severity: "none" | "minor" | "major";
  contention_note: string;
}

export interface SubmissionDetail {
  id: string;
  submission_code: string;
  status: SubmissionStatus;
  created_at: string;
  notes: string | null;
  auto_publish: boolean | null;
  card: Card | null;
  analysis_results: AnalysisResult[];
  company_comparisons: Comparison[];
}

export interface SubmissionCreate {
  game: string;
  card_name: string;
  set_name?: string;
  card_number?: string;
  foil?: boolean;
}

export interface Game {
  game: string;
  verified: boolean;
}

export interface Settings {
  auto_publish_default: boolean;
  business_name: string;
  business_logo_path: string | null;
  business_contact: string | null;
  disclaimer_text: string;
}

export interface SettingsUpdate {
  auto_publish_default?: boolean;
  business_name?: string;
  business_logo_path?: string | null;
  business_contact?: string | null;
  disclaimer_text?: string;
}

export interface Stats {
  total_submissions: number;
  by_status: Record<string, number>;
  published_reports: number;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = body.detail ?? message;
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function authHeaders(token: string): HeadersInit {
  return { Authorization: `Bearer ${token}` };
}

export async function register(email: string, password: string): Promise<User> {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function login(
  email: string,
  password: string
): Promise<{ access_token: string; token_type: string }> {
  const body = new URLSearchParams();
  body.set("username", email);
  body.set("password", password);
  return request("/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: body.toString(),
  });
}

export async function verifyEmail(token: string): Promise<User> {
  return request(`/auth/verify/${token}`, { method: "POST" });
}

export async function getMe(token: string): Promise<User> {
  return request("/auth/me", { headers: authHeaders(token) });
}

export async function getGames(): Promise<Game[]> {
  return request("/catalog/games");
}

export async function createSubmission(token: string, payload: SubmissionCreate): Promise<SubmissionDetail> {
  return request("/submissions", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function listSubmissions(token: string): Promise<SubmissionSummary[]> {
  return request("/submissions", { headers: authHeaders(token) });
}

export async function getSubmission(token: string, code: string): Promise<SubmissionDetail> {
  return request(`/submissions/${code}`, { headers: authHeaders(token) });
}

export async function downloadReport(token: string, code: string): Promise<Blob> {
  const res = await fetch(`${API_BASE}/submissions/${code}/report`, { headers: authHeaders(token) });
  if (!res.ok) {
    throw new ApiError(res.status, "Report not available yet");
  }
  return res.blob();
}

export async function approveSubmission(token: string, code: string): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/approve`, { method: "POST", headers: authHeaders(token) });
}

export async function setAutoPublish(
  token: string,
  code: string,
  autoPublish: boolean | null
): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/auto-publish`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ auto_publish: autoPublish }),
  });
}

export async function getSettings(token: string): Promise<Settings> {
  return request("/admin/settings", { headers: authHeaders(token) });
}

export async function updateSettings(token: string, payload: SettingsUpdate): Promise<Settings> {
  return request("/admin/settings", {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function getStats(token: string): Promise<Stats> {
  return request("/admin/stats", { headers: authHeaders(token) });
}
