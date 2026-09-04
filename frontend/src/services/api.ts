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
  /** A few representative tags seen on mentions in this slice (see
   *  IssueMention.tags on the backend) — the concrete dimension of an issue
   *  (e.g. "pricing") without changing its category. */
  tags: string[];
  /** Issue-category rows only: how many calls raised this as praise vs. a
   *  problem. Only set when a category genuinely appears on BOTH sides —
   *  e.g. praised on some calls, complained about on others. */
  positive_calls: number | null;
  negative_calls: number | null;
  /** Of the calls that raised it at all, the % that raised it as a problem. */
  negative_share: number | null;
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

export interface AgentStats {
  agent_name: string;
  calls_handled: number;
  average_rating: number | null;
  average_stated_rating: number | null;
  sentiment: ApiSlice[];
  satisfaction_bands: ApiSlice[];
  script_adherence: ApiSlice[];
  compliance_issue_count: number;
  connection_issue_rate: number;
}

export type RatingSource = 'ai' | 'stated';

/** The dashboard's interactive cross-filters — one optional value per
 *  clickable dimension. Every one is set by clicking a slice/row on a KPI card
 *  and cleared by clicking it again or removing its chip.
 *
 *  The key names match the backend query params exactly (see
 *  routes_dashboard.KpiFilters), which is what lets `filterParams()` below
 *  serialize them without a mapping table. */
export interface DashboardFilters {
  plant: string | null;
  agent: string | null;
  sentiment: string | null;
  connection: string | null;
  band: string | null;
  quality: string | null;
  adherence: string | null;
  category: string | null;
}

/** The dimensions a KPI card can own — everything in DashboardFilters except
 *  `plant`, which has its own dropdown rather than a clickable card. */
export type FilterKey = Exclude<keyof DashboardFilters, 'plant'>;

export const EMPTY_FILTERS: DashboardFilters = {
  plant: null,
  agent: null,
  sentiment: null,
  connection: null,
  band: null,
  quality: null,
  adherence: null,
  category: null,
};

function filterParams(filters: DashboardFilters): URLSearchParams {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(filters)) {
    if (value) query.set(key, value);
  }
  return query;
}

/** 'live' (default): real calls only. 'synthetic': only Admin-generated dummy
 *  calls, for QA without touching real data or spending on the real pipeline.
 *  'all': both. */
export type DataMode = 'live' | 'synthetic' | 'all';

export interface DashboardSummary {
  range: string;
  /** Echoes the requested plant filter; null when showing all plants combined. */
  plant: string | null;
  /** Echoes the requested agent filter; null when every agent is combined.
   *  When set, every field below is scoped to that agent's calls (except
   *  by_agent, which always stays the full roster — see AgentStats). */
  agent: string | null;
  /** Echoes the requested rating source ('ai' | 'stated'). */
  rating_source: RatingSource;
  /** Echoes the requested data mode. */
  data_mode: DataMode;
  /** Every active cross-filter, echoed back — what the chip row renders.
   *
   *  Note each breakdown below is computed with every active filter applied
   *  EXCEPT its own dimension, so a card you filtered by stays showing its
   *  full breakdown (with the chosen slice highlighted) and remains clickable
   *  in both directions. */
  filters: Omit<DashboardFilters, 'plant'>;
  /** Every recording discovered in range, including ones never analyzed yet. */
  total_calls: number;
  /** Recordings with an analysis row of any kind. */
  analyzed_calls: number;
  /** Analyzed and intelligible — INCLUDES busy tones and voicemails, which are
   *  clear recordings of nothing. Only Connection Quality uses this. */
  reachable_calls: number;
  /** Reachable AND a customer actually spoke. The "Based on N Usable Calls"
   *  denominator everywhere else — a busy tone has no opinion to measure. */
  usable_calls: number;
  average_rating: number | null;
  call_quality: ApiSlice[];
  /** How the call itself went technically (connected/dropped/no-answer/etc.),
   *  independent of recording clarity — see call_quality for that. */
  connection_status: ApiSlice[];
  sentiment: ApiSlice[];
  satisfaction_bands: ApiSlice[];
  script_adherence: ApiSlice[];
  top_negative_drivers: ApiSlice[];
  top_service_issues: ApiSlice[];
  top_positive_themes: ApiSlice[];
  top_compliance_issues: ApiSlice[];
  by_agent: AgentStats[];
  current_month_label: string | null;
  monthly_averages: ApiMonthlyAverage[];
  daily_ratings: ApiDailyRating[];
}

export interface InsightPair {
  positive_category: string;
  other_category: string;
  other_mention_type: string;
  count: number;
  percentage: number;
  positive_example: string | null;
  other_example: string | null;
}

export interface DashboardInsights {
  range: string;
  plant: string | null;
  agent: string | null;
  data_mode: DataMode;
  usable_calls: number;
  insights: InsightPair[];
}

export interface SyntheticDataStatus {
  live_calls: number;
  synthetic_calls: number;
}

/** One node of the analysis flow (backend/app/pipeline/kpi_registry.py). */
export interface KpiNode {
  key: string;
  label: string;
  description: string;
  version: string;
  /** 'transcription' = the strong, audio-reading model (one node, runs once
   *  per recording, checkpointed). 'extraction' = the cheap text tier. */
  tier: 'transcription' | 'extraction';
  /** The model this tier currently resolves to. */
  model: string;
  enabled: boolean;
  /** Required nodes can't be switched off — everything else reads their output. */
  required: boolean;
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

export interface DashboardAgents {
  /** Every distinct agent name seen in the data, for filter/breakdown option lists. */
  agents: string[];
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

export interface DeepHealthProbe {
  name: string;
  status: string;
  detail: string;
}

export interface DeepHealthStatus {
  status: string;
  probes: DeepHealthProbe[];
}

export interface ScheduleConfig {
  enabled: boolean;
  run_hour: number;
  run_minute: number;
  /** null = uses the backend's PIPELINE_RUN_LIMIT; 0 = no cap. */
  run_limit: number | null;
  last_run_at: string | null;
  last_run_status: string | null;
  last_run_summary: string | null;
}

export interface ScheduleConfigUpdate {
  enabled: boolean;
  run_hour: number;
  run_minute: number;
  run_limit: number | null;
}

export interface CallAnalysisSummary {
  call_quality: string;
  connection_status: string;
  sentiment: string;
  sentiment_summary: string | null;
  satisfaction_rating: number;
  customer_stated_rating: number | null;
  agent_name: string | null;
  script_adherence: string;
  summary: string | null;
}

export interface CallListItem {
  id: string;
  object_name: string;
  team_code: string | null;
  recording_date: string | null;
  status: string;
  is_synthetic: boolean;
  created_at: string;
  analysis: CallAnalysisSummary | null;
}

export interface CallTranscript {
  /** Verbatim, as spoken — a code-mixed Hindi/English call stays code-mixed. */
  text: string;
  /** The same conversation in English, produced by the transcription node.
   *  Null on calls analyzed before that step existed. */
  english_text: string | null;
  language_code: string | null;
  confidence: number | null;
}

export interface CallMention {
  mention_type: string;
  category: string;
  quote: string | null;
  tags: string[];
}

export interface CallDetail extends CallListItem {
  transcript: CallTranscript | null;
  mentions: CallMention[];
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
  filters: DashboardFilters,
  ratingSource: RatingSource = 'ai',
  dataMode: DataMode = 'live',
): Promise<DashboardSummary> {
  const query = filterParams(filters);
  query.set('range', range);
  query.set('rating_source', ratingSource);
  query.set('data_mode', dataMode);
  return request<DashboardSummary>(`/api/dashboard/summary?${query}`);
}

export function fetchDashboardInsights(
  range: TimeRangeKey,
  filters: DashboardFilters,
  dataMode: DataMode = 'live',
): Promise<DashboardInsights> {
  const query = filterParams(filters);
  query.set('range', range);
  query.set('data_mode', dataMode);
  return request<DashboardInsights>(`/api/dashboard/insights?${query}`);
}

export function fetchDashboardPlants(dataMode: DataMode = 'live'): Promise<DashboardPlants> {
  return request<DashboardPlants>(`/api/dashboard/plants?data_mode=${dataMode}`);
}

export function fetchDashboardAgents(dataMode: DataMode = 'live'): Promise<DashboardAgents> {
  return request<DashboardAgents>(`/api/dashboard/agents?data_mode=${dataMode}`);
}

/** Cheapest possible touch of the calls router, for the Admin tab's endpoint
 *  health table — the response body itself isn't used. */
export function pingCallsEndpoint(): Promise<unknown> {
  return request<unknown>('/api/calls?limit=1');
}

export type CallSortKey =
  | 'created_at'
  | 'recording_date'
  | 'team_code'
  | 'agent_name'
  | 'status'
  | 'call_quality'
  | 'sentiment'
  | 'satisfaction_rating';

export interface CallFilters {
  status?: string;
  call_quality?: string;
  sentiment?: string;
  agent_name?: string;
  rating_min?: number;
  rating_max?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
  /** Calls carrying a mention of this exact category, any mention type. What
   *  the dashboard's issue tables link through to. */
  category?: string;
  /** Calls carrying a mention with this tag — cuts across categories. */
  tag?: string;
  /** How the call connected. The dashboard's KPIs exclude non-conversation
   *  states; this is how you still get at those recordings to check them. */
  connection_status?: string;
  script_adherence?: string;
  /** Restrict to calls where a customer actually spoke (see
   *  DashboardSummary.usable_calls). Needed to keep rating_min/rating_max
   *  review links exact — a non-conversation call's satisfaction_rating is a
   *  meaningless placeholder that would otherwise get swept into a "1-7"
   *  review by coincidence. */
  conversations_only?: boolean;
}

export function fetchCalls(params: {
  limit: number;
  offset: number;
  plant: string | null;
  sortBy?: CallSortKey;
  sortDir?: 'asc' | 'desc';
  filters?: CallFilters;
  dataMode?: DataMode;
}): Promise<CallListItem[]> {
  const query = new URLSearchParams({
    limit: String(params.limit),
    offset: String(params.offset),
    data_mode: params.dataMode ?? 'live',
  });
  if (params.plant) query.set('plant', params.plant);
  if (params.sortBy) query.set('sort_by', params.sortBy);
  if (params.sortDir) query.set('sort_dir', params.sortDir);
  for (const [key, value] of Object.entries(params.filters ?? {})) {
    if (value !== undefined && value !== null && value !== '') query.set(key, String(value));
  }
  return request<CallListItem[]>(`/api/calls?${query}`);
}

export function fetchCallDetail(id: string): Promise<CallDetail> {
  return request<CallDetail>(`/api/calls/${id}`);
}

/** Direct-use src for an <audio> tag — the browser fetches this itself, no
 *  need to route it through the JSON `request()` wrapper. */
export function callAudioUrl(id: string): string {
  return `${API_BASE_URL}/api/calls/${id}/audio`;
}

export function fetchPipelineStatus(): Promise<PipelineStatus> {
  return request<PipelineStatus>('/api/pipeline/status');
}

export function fetchHealth(): Promise<HealthStatus> {
  return request<HealthStatus>('/api/health');
}

/** Deep probe: actually exercises DB, GCS and Gemini — costs a Gemini call.
 *  Manual-trigger only, never auto-polled. See backend routes_health.py. */
export function fetchDeepHealth(): Promise<DeepHealthStatus> {
  return request<DeepHealthStatus>('/api/health/all');
}

export function fetchScheduleConfig(): Promise<ScheduleConfig> {
  return request<ScheduleConfig>('/api/admin/schedule');
}

export function updateScheduleConfig(update: ScheduleConfigUpdate): Promise<ScheduleConfig> {
  return request<ScheduleConfig>('/api/admin/schedule', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
}

/** `limitOverride` wins when given (used by the Admin tab's manual-run
 *  control); otherwise falls back to VITE_PIPELINE_LIMIT as before. `force`
 *  re-analyzes already-ANALYZED calls too — the deliberate one-off backfill
 *  path after a prompt/schema change, off by default. */
export async function runAnalysisPipeline(
  limitOverride?: number,
  force = false,
): Promise<PipelineRunSummary> {
  const limit = limitOverride ?? (PIPELINE_LIMIT === undefined ? undefined : Number(PIPELINE_LIMIT));
  const query = new URLSearchParams();
  if (limit !== undefined) query.set('limit', String(limit));
  if (force) query.set('force', 'true');
  const qs = query.toString();
  return request<PipelineRunSummary>(`/api/pipeline/run${qs ? `?${qs}` : ''}`, { method: 'POST' });
}

/** What the button should promise before it's been clicked. `null` = uncapped. */
export function configuredRunLimit(): number | null {
  if (PIPELINE_LIMIT === undefined) return null;
  const parsed = Number(PIPELINE_LIMIT);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
}

export function fetchSyntheticDataStatus(): Promise<SyntheticDataStatus> {
  return request<SyntheticDataStatus>('/api/admin/synthetic-data');
}

/** Generates `count` dummy calls entirely on the backend — no GCS/Gemini
 *  calls, so this costs nothing. For previewing dashboard/KPI changes via
 *  the Data Mode selector without touching real data. */
export function generateSyntheticData(count: number): Promise<SyntheticDataStatus> {
  return request<SyntheticDataStatus>(`/api/admin/synthetic-data?count=${count}`, { method: 'POST' });
}

export function clearSyntheticData(): Promise<SyntheticDataStatus> {
  return request<SyntheticDataStatus>('/api/admin/synthetic-data', { method: 'DELETE' });
}

/** The analysis flow as it will next run — one entry per node, in graph order. */
export function fetchKpiNodes(): Promise<KpiNode[]> {
  return request<KpiNode[]>('/api/admin/kpis');
}

/** Switches one node on or off for the next run. Takes effect on
 *  already-analyzed calls only via a forced re-run — which is cheap, since the
 *  transcript comes from the checkpoint and only this node calls a model. */
export function updateKpiNode(key: string, enabled: boolean): Promise<KpiNode> {
  return request<KpiNode>(`/api/admin/kpis/${key}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ enabled }),
  });
}
