import type { TimeRangeKey } from '../types/dashboard.types';

/**
 * Default: '' (relative — requests go to the page's own origin). Correct for
 * the normal deployment, where FastAPI serves this built frontend itself
 * (start-prod.bat) — same origin regardless of which port that happens to be
 * on, so nothing here needs to know it. Only set VITE_API_BASE_URL when the
 * frontend is served from somewhere OTHER than the backend, e.g. the Vite dev
 * server (start.bat) proxies /api to localhost:8000 by default — see
 * vite.config.ts — so override this only if that backend runs on a different
 * port.
 */
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/**
 * Recordings sent to Gemini per click of "Run Analysis".
 *
 * A spend guard, not a page size: the bucket holds well over a hundred
 * recordings and each one costs a model call, so an uncapped button is a
 * surprising bill one misclick away. Leave unset to use the backend's own
 * PIPELINE_RUN_LIMIT; set VITE_PIPELINE_LIMIT=0 to lift the cap entirely.
 */
const PIPELINE_LIMIT = import.meta.env.VITE_PIPELINE_LIMIT;

// --- Wire types (mirror backend/app/schemas/) ---------------------------

export interface ApiSlice {
  /** Stable machine value — an enum value like "good_clear", or a category
   *  name. Colors and icons key off this, never off `label`. */
  key: string;
  label: string;
  count: number;
  percentage: number;
  example: string | null;
}

export interface ApiMonthlyAverage {
  month: string;
  avg_rating: number;
  call_count: number;
}

export interface ApiDailyRating {
  day: number;
  rating: number;
  call_count: number;
}

export interface DashboardSummary {
  range: string;
  /** Echoes the requested plant filter; null when showing all plants combined. */
  plant: string | null;
  /** Every recording discovered in range, including ones never analyzed yet. */
  total_calls: number;
  /** Recordings with an analysis row of any kind. */
  analyzed_calls: number;
  /** Analyzed AND intelligible — the "Based on N Usable Calls" denominator. */
  usable_calls: number;
  average_rating: number | null;
  call_quality: ApiSlice[];
  sentiment: ApiSlice[];
  satisfaction_bands: ApiSlice[];
  top_negative_drivers: ApiSlice[];
  top_service_issues: ApiSlice[];
  top_positive_themes: ApiSlice[];
  current_month_label: string | null;
  monthly_averages: ApiMonthlyAverage[];
  daily_ratings: ApiDailyRating[];
}

export interface PipelineRunSummary {
  found_in_bucket: number;
  already_processed: number;
  newly_processed: number;
  /** Subset of newly_processed that never reached the model (audio too small to contain speech). */
  skipped_by_prescreen: number;
  failed: number;
  /** Recordings this run was allowed to send to Gemini; null = no cap. */
  limit_applied: number | null;
  /** Deferred by that cap — what the next click picks up. */
  remaining_pending: number;
  errors: string[];
}

export interface DashboardPlants {
  /** Every plant code seen in the data (e.g. ["CE", "TA"]), for the filter's
   *  own option list — independent of any range/plant currently selected. */
  plants: string[];
}

export interface PipelineStatus {
  total_calls: number;
  analyzed: number;
  failed: number;
  not_yet_analyzed: number;
  default_run_limit: number;
}

export interface HealthStatus {
  status: string;
  database: string;
  gemini_api_key: string;
  gcs_bucket: string;
  model: string;
}

// --- Client -------------------------------------------------------------

/**
 * The backend reports failures as `{"detail": "..."}`. Surfacing that beats
 * showing a raw JSON blob or a bare status code — when this fails it's
 * usually a misconfigured machine (no DB, no API key), and the detail says
 * which.
 */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    // fetch only rejects for network-level failures, which here means the
    // API isn't running — worth saying plainly rather than "Failed to fetch".
    throw new Error(`Cannot reach the backend at ${API_BASE_URL}. Is it running?`);
  }

  if (!response.ok) {
    const detail = await response
      .json()
      .then((body: { detail?: string }) => body.detail)
      .catch(() => undefined);
    throw new Error(`${detail ?? response.statusText} (HTTP ${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function fetchDashboardSummary(
  range: TimeRangeKey,
  plant: string | null,
): Promise<DashboardSummary> {
  const query = plant ? `range=${range}&plant=${plant}` : `range=${range}`;
  return request<DashboardSummary>(`/api/dashboard/summary?${query}`);
}

export function fetchDashboardPlants(): Promise<DashboardPlants> {
  return request<DashboardPlants>('/api/dashboard/plants');
}

export function fetchPipelineStatus(): Promise<PipelineStatus> {
  return request<PipelineStatus>('/api/pipeline/status');
}

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health');
}

export async function runAnalysisPipeline(): Promise<PipelineRunSummary> {
  const query = PIPELINE_LIMIT === undefined ? '' : `?limit=${Number(PIPELINE_LIMIT)}`;
  return request<PipelineRunSummary>(`/api/pipeline/run${query}`, { method: 'POST' });
}

/** What the button should promise before it's been clicked. `null` = uncapped. */
export function configuredRunLimit(): number | null {
  if (PIPELINE_LIMIT === undefined) return null;
  const parsed = Number(PIPELINE_LIMIT);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}
