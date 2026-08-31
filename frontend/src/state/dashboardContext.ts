import { createContext, useContext, useEffect } from 'react';
import type { DashboardSummary } from '../services/api';
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
  /** Selected plant filter (e.g. "CE" / "TA"); null = every plant combined.
   *  Global, unlike time range: one dropdown affects every card on the page. */
  plant: string | null;
  entries: Record<string, SummaryState>;
}

export interface DashboardDataValue {
  store: Store;
  plants: string[];
  ensure: (range: TimeRangeKey) => void;
  setPlant: (plant: string | null) => void;
  refresh: () => void;
  refreshedAt: Date | null;
}

export const DashboardDataContext = createContext<DashboardDataValue | null>(null);

export const cacheKey = (version: number, plant: string | null, range: TimeRangeKey) =>
  `${version}:${plant ?? 'all'}:${range}`;

function useDashboardData(): DashboardDataValue {
  const context = useContext(DashboardDataContext);
  if (!context) {
    throw new Error('useDashboardData must be used inside <DashboardDataProvider>');
  }
  return context;
}

export function useDashboardSummary(range: TimeRangeKey): SummaryState {
  const { store, ensure } = useDashboardData();
  const { version, plant, entries } = store;

  // `version` and `plant` are dependencies so a refresh re-requests the range
  // this component is showing, and changing the plant filter re-requests it
  // under the new plant, rather than only reacting to `range` changing.
  useEffect(() => {
    ensure(range);
  }, [ensure, range, version, plant]);

  return entries[cacheKey(version, plant, range)] ?? { status: 'loading' };
}

/** The global plant filter — one control, shared by every card on the page. */
export function usePlantFilter(): {
  plant: string | null;
  setPlant: (plant: string | null) => void;
  plants: string[];
} {
  const { store, setPlant, plants } = useDashboardData();
  return { plant: store.plant, setPlant, plants };
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
