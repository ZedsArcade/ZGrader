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
  display_name: string | null;
  marketing_consent: boolean;
  terms_accepted_at: string | null;
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

// Lives inside a non-"combined" AnalysisResult's measurements.regions --
// see backend/zgrader/analysis/regions.py for how these are built.
export interface Region {
  id: string;
  kind: "corner" | "edge" | "frame" | "blob";
  severity: "flag" | "ok";
  score: number;
  bbox_norm: [number, number, number, number];
  anchor_norm: [number, number];
  note: string | null;
  // Set on a centering "frame" region when the measurement is unreliable
  // (holo/full-art card with no clean printed border) -- the UI draws it
  // muted/dashed instead of asserting a precise centering box.
  low_confidence?: boolean;
  // [x0, y0, x1, y1] normalized: an elongated defect's actual segment (a
  // crease). Its bounding box spans most of the card, so the line is what
  // shows where it really runs.
  line_norm?: [number, number, number, number];
}

export interface Comparison {
  company: "PSA" | "BGS" | "CGC" | "TAG";
  category: string;
  severity: "none" | "minor" | "major";
  contention_note: string;
}

export type ScanSide = "front" | "back";

export interface SubmissionDetail {
  id: string;
  submission_code: string;
  status: SubmissionStatus;
  created_at: string;
  notes: string | null;
  auto_publish: boolean | null;
  card: Card | null;
  scan_sides: ScanSide[];
  confirmed_sides: ScanSide[];
  // "{side}:{category}:{region_id}" keys the client dismissed as mistaken
  // auto-detections; the scores/comparisons here already reflect them.
  dismissed_regions: string[];
  analysis_results: AnalysisResult[];
  company_comparisons: Comparison[];
}

// A [x, y] pixel point in a scan's own raw-image coordinate space --
// ScanImage.crop_points on the backend.
export type CropPoint = [number, number];

export interface CropSuggestion {
  points: CropPoint[];
  width_px: number;
  height_px: number;
}

export interface SubmissionCreate {
  game: string;
  card_name: string;
  set_name?: string;
  card_number?: string;
  foil?: boolean;
  language?: "en" | "es";
}

export interface Game {
  game: string;
  verified: boolean;
}

/** Public contact details shown in the nav, footer and contact page. Every
 *  optional field is hidden by the UI when null, so an operator who hasn't
 *  filled one in never ships a dead link. */
export interface PublicContact {
  contact_email: string | null;
  contact_location: string | null;
  contact_response_days: number | null;
  contact_in_person: boolean;
  social_instagram: string | null;
  social_facebook: string | null;
  social_x: string | null;
  social_whatsapp: string | null;
}

export interface Branding extends PublicContact {
  business_name: string;
  business_contact: string | null;
  /** Companies currently taking part in the comparison, in a fixed order.
   *  The public copy names these rather than a hardcoded list, so disabling
   *  one in admin can't leave the site advertising a comparison it no longer
   *  runs. */
  grading_companies: string[];
}

export interface GradingCompanyStatus {
  company: string;
  active: boolean;
  rule_count: number;
}

export interface Settings extends PublicContact {
  auto_publish_default: boolean;
  business_name: string;
  business_logo_path: string | null;
  business_contact: string | null;
  disclaimer_text: string;
}

export interface SettingsUpdate extends Partial<PublicContact> {
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

export interface AuditLogEntry {
  id: string;
  created_at: string;
  action: string;
  detail: Record<string, unknown>;
  submission_code: string | null;
  user_email: string | null;
}

/** FastAPI reports most failures as a `detail` string, but validation errors
 *  (422) send a list of `{loc, msg}` objects instead. Interpolating that
 *  straight into a message produced "[object Object]" on screen, which tells
 *  the user nothing -- so name the offending field and quote the reason. */
function describeDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (!Array.isArray(detail)) return null;
  const parts = detail
    .map((item) => {
      if (typeof item !== "object" || item === null) return null;
      const { loc, msg } = item as { loc?: unknown[]; msg?: string };
      if (!msg) return null;
      // loc is like ["body", "social_x"]; the last entry is the field.
      const field = Array.isArray(loc) ? loc[loc.length - 1] : undefined;
      const label = typeof field === "string" && field !== "body" ? `${field}: ` : "";
      return `${label}${msg.replace(/^Value error, /, "")}`;
    })
    .filter((p): p is string => Boolean(p));
  return parts.length > 0 ? parts.join("; ") : null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, options);
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      message = describeDetail(body.detail) ?? message;
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

export async function register(
  email: string,
  password: string,
  acceptTerms: boolean,
  marketingConsent = false
): Promise<User> {
  return request("/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password,
      accept_terms: acceptTerms,
      marketing_consent: marketingConsent,
    }),
  });
}

const jsonPost = (path: string, body: unknown, token?: string) =>
  request<void>(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? authHeaders(token) : {}),
    },
    body: JSON.stringify(body),
  });

export async function requestPasswordReset(email: string): Promise<void> {
  return jsonPost("/auth/forgot-password", { email });
}

export async function resetPassword(token: string, password: string): Promise<void> {
  return jsonPost("/auth/reset-password", { token, password });
}

export async function resendVerification(email: string): Promise<void> {
  return jsonPost("/auth/verify/resend", { email });
}

export async function changePassword(
  token: string,
  currentPassword: string,
  newPassword: string
): Promise<{ access_token: string; token_type: string }> {
  return request("/auth/change-password", {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function updateProfile(
  token: string,
  updates: { display_name?: string | null; marketing_consent?: boolean }
): Promise<User> {
  return request("/auth/me", {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify(updates),
  });
}

export async function deleteAccount(token: string): Promise<void> {
  return request("/auth/me", { method: "DELETE", headers: authHeaders(token) });
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

export async function getBranding(): Promise<Branding> {
  return request("/catalog/branding");
}

/** Slugs identifying the six service tiers on /services. Must stay in step
 *  with SERVICE_TIER_SLUGS in backend/zgrader/images.py -- the backend 404s
 *  anything it doesn't recognise. */
export type ServiceSlug =
  | "analysis"
  | "subscription"
  | "personalised"
  | "restoration"
  | "packaging"
  | "collection";

/** Which tiers have a banner, mapped to a version (the file's mtime). */
export type ServiceImageVersions = Partial<Record<ServiceSlug, number>>;

export async function getServiceImages(): Promise<ServiceImageVersions> {
  return request("/catalog/service-images");
}

/** Unlike every other image URL here, this one is public, so it can go
 *  straight into an <img src> with no token and no blob dance. The version
 *  makes a replaced image a new URL, so it can be cached hard and still
 *  update the moment the operator uploads a new one. */
export function serviceImageUrl(slug: ServiceSlug, version: number): string {
  return `${API_BASE}/catalog/service-images/${slug}?v=${version}`;
}

export async function uploadServiceImage(
  token: string,
  slug: ServiceSlug,
  file: File
): Promise<void> {
  const body = new FormData();
  body.set("file", file);
  // No Content-Type header -- the browser has to set the multipart boundary.
  return request(`/admin/service-images/${slug}`, {
    method: "PUT",
    headers: authHeaders(token),
    body,
  });
}

export async function deleteServiceImage(token: string, slug: ServiceSlug): Promise<void> {
  return request(`/admin/service-images/${slug}`, {
    method: "DELETE",
    headers: authHeaders(token),
  });
}

export async function getGradingCompanies(token: string): Promise<GradingCompanyStatus[]> {
  return request("/admin/grading-companies", { headers: authHeaders(token) });
}

export async function setGradingCompanyActive(
  token: string,
  company: string,
  active: boolean
): Promise<GradingCompanyStatus> {
  return request(`/admin/grading-companies/${company}`, {
    method: "PATCH",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ active }),
  });
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

export async function deleteSubmission(token: string, code: string): Promise<void> {
  await request(`/submissions/${code}`, { method: "DELETE", headers: authHeaders(token) });
}

export async function uploadScan(
  token: string,
  code: string,
  side: ScanSide,
  file: File
): Promise<SubmissionDetail> {
  const body = new FormData();
  body.set("side", side);
  body.set("file", file);
  // No Content-Type header here -- the browser sets the multipart boundary
  // itself; setting one manually (as every JSON call above does) breaks it.
  return request(`/submissions/${code}/scans`, {
    method: "POST",
    headers: authHeaders(token),
    body,
  });
}

// Every endpoint requires a Bearer token -- there's no cookie auth -- so a
// plain <img src="..."> would 401. Every image consumer (report PDF, side
// photos, region crops) fetches the bytes with this helper instead and
// hands the caller a Blob to turn into an object URL.
export async function fetchAuthedImage(
  token: string,
  url: string,
  notFoundMessage = "Image not available"
): Promise<Blob> {
  const res = await fetch(url, { headers: authHeaders(token) });
  if (!res.ok) {
    throw new ApiError(res.status, notFoundMessage);
  }
  return res.blob();
}

export function sidePhotoUrl(code: string, side: ScanSide): string {
  return `${API_BASE}/submissions/${code}/scans/${side}/photo`;
}

export function regionCropUrl(code: string, side: ScanSide, category: string, regionId: string): string {
  return `${API_BASE}/submissions/${code}/scans/${side}/regions/${category}/${regionId}/crop`;
}

export function rawScanUrl(code: string, side: ScanSide): string {
  return `${API_BASE}/submissions/${code}/scans/${side}/raw`;
}

export async function suggestCrop(token: string, code: string, side: ScanSide): Promise<CropSuggestion> {
  return request(`/submissions/${code}/scans/${side}/suggest-crop`, { headers: authHeaders(token) });
}

export async function confirmCrop(
  token: string,
  code: string,
  side: ScanSide,
  points: CropPoint[]
): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/scans/${side}/confirm-crop`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ points }),
  });
}

export async function snapCrop(
  token: string,
  code: string,
  side: ScanSide,
  points: CropPoint[]
): Promise<{ points: CropPoint[] }> {
  return request(`/submissions/${code}/scans/${side}/snap-crop`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ points }),
  });
}

export async function toggleRegion(
  token: string,
  code: string,
  regionKey: string,
  dismissed: boolean
): Promise<SubmissionDetail> {
  return request(`/submissions/${code}/regions/toggle`, {
    method: "POST",
    headers: { ...authHeaders(token), "Content-Type": "application/json" },
    body: JSON.stringify({ region_key: regionKey, dismissed }),
  });
}

export async function downloadReport(token: string, code: string): Promise<Blob> {
  return fetchAuthedImage(token, `${API_BASE}/submissions/${code}/report`, "Report not available yet");
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

export async function getAuditLog(
  token: string,
  { limit = 50, offset = 0 }: { limit?: number; offset?: number } = {}
): Promise<AuditLogEntry[]> {
  return request(`/admin/audit-log?limit=${limit}&offset=${offset}`, { headers: authHeaders(token) });
}
