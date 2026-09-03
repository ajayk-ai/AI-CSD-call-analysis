import { createContext, useContext, useEffect } from 'react';
import type {
  DashboardFilters,
  DashboardSummary,
  DataMode,
  FilterKey,
  RatingSource,
} from '../services/api';
import type { TimeRangeKey } from '../types/dashboard.types';

/**
 * Context, hooks and cache-key helpers for the shared dashboard summary.
 *
 * Split out from the provider component so that file exports components only —
 * mixing components and plain functions in one module breaks React Fast
 * Refresh, which would make every edit here a full page reload.
 */

export type SummaryState =
  | { status: 'loading'; stale?: DashboardSummary }
  | { status: 'ready'; data: DashboardSummary }
  | { status: 'error'; message: string };

export interface Store {
  version: number;
  /** Every global filter, in one object.
   *
   *  All of these are global in the sense the time range isn't: one selection
   *  affects every card on the page. `plant` has its own dropdown; the rest
   *  are set by clicking a slice or row on a KPI card, which is what makes the
   *  dashboard drillable — every card reading through useDashboardSummary
   *  recontextualizes around the selection automatically, because the backend
   *  does the scoping (see routes_dashboard.KpiFilters).
   *
   *  Each card that OWNS a dimension is the exception, and deliberately so:
   *  it keeps showing its full breakdown so the selection stays changeable
   *  from where it was made. AgentPerformanceTable works the same way for
   *  `agent`. */
  filters: DashboardFilters;
  /** 'live' (default) | 'synthetic' | 'all' — global, set from the Admin
   *  tab's Synthetic Data panel, so every card switches together rather than
   *  mixing real and dummy numbers on the same screen. */
  dataMode: DataMode;
  entries: Record<string, SummaryState>;
}

export interface DashboardDataValue {
  store: Store;
  plants: string[];
  agents: string[];
  ensure: (range: TimeRangeKey, ratingSource?: RatingSource) => void;
  setFilter: (key: keyof DashboardFilters, value: string | null) => void;
  clearFilters: () => void;
  setDataMode: (mode: DataMode) => void;
  refresh: () => void;
  refreshedAt: Date | null;
}

export const DashboardDataContext = createContext<DashboardDataValue | null>(null);

export const cacheKey = (
  version: number,
  filters: DashboardFilters,
  range: TimeRangeKey,
  ratingSource: RatingSource = 'ai',
  dataMode: DataMode = 'live',
) =>
  [
    version,
    range,
    ratingSource,
    dataMode,
    // Serialized rather than spelled out field by field, so adding a filter
    // dimension can't silently leave it out of the key and serve one
    // selection's data under another's.
    JSON.stringify(filters),
  ].join(':');

function useDashboardData(): DashboardDataValue {
  const context = useContext(DashboardDataContext);
  if (!context) {
    throw new Error('useDashboardData must be used inside <DashboardDataProvider>');
  }
  return context;
}

export function useDashboardSummary(range: TimeRangeKey, ratingSource: RatingSource = 'ai'): SummaryState {
  const { store, ensure } = useDashboardData();
  const { version, filters, dataMode, entries } = store;
  const key = cacheKey(version, filters, range, ratingSource, dataMode);

  // Depending on the computed key (rather than on each field) means adding a
  // filter dimension needs no change here: any selection change produces a new
  // key and re-requests, and a refresh does the same via `version`.
  useEffect(() => {
    ensure(range, ratingSource);
  }, [ensure, range, ratingSource, key]);

  return entries[key] ?? { status: 'loading' };
}

/** Every global filter at once, plus the two setters. Cards that own a
 *  dimension use this; most cards don't need it at all, since the data they
 *  already read through useDashboardSummary is scoped for them. */
export function useDashboardFilters(): {
  filters: DashboardFilters;
  setFilter: (key: keyof DashboardFilters, value: string | null) => void;
  clearFilters: () => void;
} {
  const { store, setFilter, clearFilters } = useDashboardData();
  return { filters: store.filters, setFilter, clearFilters };
}

/** One clickable KPI dimension.
 *
 *  `toggle` is the whole interaction: clicking the selected slice clears it,
 *  clicking a different one switches to it. Cards call this rather than
 *  reimplementing the same three-line comparison each time.
 */
export function useKpiFilter(key: FilterKey): {
  value: string | null;
  toggle: (next: string) => void;
  isActive: (candidate: string) => boolean;
} {
  const { store, setFilter } = useDashboardData();
  const value = store.filters[key];
  return {
    value,
    toggle: (next: string) => setFilter(key, value === next ? null : next),
    isActive: (candidate: string) => value === candidate,
  };
}

/** The global plant filter — one dropdown, shared by every card on the page. */
export function usePlantFilter(): {
  plant: string | null;
  setPlant: (plant: string | null) => void;
  plants: string[];
} {
  const { store, setFilter, plants } = useDashboardData();
  return { plant: store.filters.plant, setPlant: (p) => setFilter('plant', p), plants };
}

/** The global agent filter — drives the dashboard's per-agent drill-down.
 *  `agents` is the full known roster (unaffected by the current selection),
 *  for populating the picker. */
export function useAgentFilter(): {
  agent: string | null;
  setAgent: (agent: string | null) => void;
  agents: string[];
} {
  const { store, setFilter, agents } = useDashboardData();
  return { agent: store.filters.agent, setAgent: (a) => setFilter('agent', a), agents };
}

/** The global data-source selector (live / synthetic / all). */
export function useDataMode(): { dataMode: DataMode; setDataMode: (mode: DataMode) => void } {
  const { store, setDataMode } = useDashboardData();
  return { dataMode: store.dataMode, setDataMode };
}

export function useDashboardRefresh(): { refresh: () => void; refreshedAt: Date | null } {
  const { refresh, refreshedAt } = useDashboardData();
  return { refresh, refreshedAt };
}

/** The data to render right now: fresh if we have it, last known otherwise. */
export function displayData(state: SummaryState): DashboardSummary | null {
  if (state.status === 'ready') return state.data;
  if (state.status === 'loading') return state.stale ?? null;
  return null;
}
