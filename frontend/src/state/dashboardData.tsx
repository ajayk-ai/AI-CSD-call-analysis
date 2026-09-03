import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  EMPTY_FILTERS,
  fetchDashboardAgents,
  fetchDashboardPlants,
  fetchDashboardSummary,
  type DashboardFilters,
  type DataMode,
  type RatingSource,
} from '../services/api';
import type { TimeRangeKey } from '../types/dashboard.types';
import { cacheKey, DashboardDataContext, type Store } from './dashboardContext';

/**
 * One shared, (filters, range, ratingSource, dataMode)-keyed cache of
 * `GET /api/dashboard/summary`.
 *
 * Two cards carry their own independent time filter, and the rest of the page
 * reads the "all" summary; every card also shares one set of global filters
 * (plant, agent, and the clickable KPI dimensions — see dashboardContext's
 * `filters` docs) and one global data-mode selector (live/synthetic/all — see
 * Admin's Synthetic Data panel). Without a shared cache that's several
 * components each firing their own request for the same combination on mount.
 *
 * "Run Analysis" bumps `version`, invalidating everything at once — the
 * pipeline moves every number on the page, so refreshing panels piecemeal
 * would leave the dashboard internally inconsistent. Changing a filter does
 * NOT bump the version: it's just a different cache key, so clicking a slice
 * and clicking it back off serves straight from cache instead of refetching.
 */
export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const [store, setStore] = useState<Store>({
    version: 0,
    filters: EMPTY_FILTERS,
    dataMode: 'live',
    entries: {},
  });
  const [plants, setPlants] = useState<string[]>([]);
  const [agents, setAgents] = useState<string[]>([]);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  // Keys already dispatched. A ref rather than state, because starting a fetch
  // must not itself trigger a render — that would re-run the effect that
  // started it.
  const dispatched = useRef(new Set<string>());

  useEffect(() => {
    fetchDashboardPlants(store.dataMode)
      .then((result) => setPlants(result.plants))
      // The filter just won't offer any options if this fails — every card
      // still renders its all-plants data, so there's nothing to surface.
      .catch(() => undefined);
    fetchDashboardAgents(store.dataMode)
      .then((result) => setAgents(result.agents))
      .catch(() => undefined);
  }, [store.dataMode]);

  const ensure = useCallback((range: TimeRangeKey, ratingSource: RatingSource = 'ai') => {
    setStore((current) => {
      const key = cacheKey(current.version, current.filters, range, ratingSource, current.dataMode);
      if (dispatched.current.has(key)) return current;
      dispatched.current.add(key);

      fetchDashboardSummary(range, current.filters, ratingSource, current.dataMode)
        .then((data) =>
          setStore((s) => ({ ...s, entries: { ...s.entries, [key]: { status: 'ready', data } } })),
        )
        .catch((error: unknown) =>
          setStore((s) => ({
            ...s,
            entries: {
              ...s.entries,
              [key]: {
                status: 'error',
                message: error instanceof Error ? error.message : 'Unknown error',
              },
            },
          })),
        );

      // Carry the previous version's data forward while the new one loads, so
      // a refresh doesn't blank the dashboard mid-run.
      const previous =
        current.entries[
          cacheKey(current.version - 1, current.filters, range, ratingSource, current.dataMode)
        ];
      return {
        ...current,
        entries: {
          ...current.entries,
          [key]: {
            status: 'loading',
            stale: previous?.status === 'ready' ? previous.data : undefined,
          },
        },
      };
    });
  }, []);

  const setFilter = useCallback((key: keyof DashboardFilters, value: string | null) => {
    // No cache invalidation needed: the filters are part of the cache key, so
    // this is just a different set of entries, not a refresh of existing ones.
    setStore((current) => ({ ...current, filters: { ...current.filters, [key]: value } }));
  }, []);

  const clearFilters = useCallback(() => {
    setStore((current) => ({ ...current, filters: EMPTY_FILTERS }));
  }, []);

  const setDataMode = useCallback((dataMode: DataMode) => {
    // Same reasoning as setPlant — dataMode is part of the cache key.
    setStore((current) => ({ ...current, dataMode }));
  }, []);

  const refresh = useCallback(() => {
    dispatched.current.clear();
    setStore((current) => ({
      ...current,
      version: current.version + 1,
      // Keep only the outgoing version — it is the stale-while-revalidate
      // source for the incoming one. Anything older can never be read again.
      entries: Object.fromEntries(
        Object.entries(current.entries).filter(([key]) => key.startsWith(`${current.version}:`)),
      ),
    }));
    setRefreshedAt(new Date());
  }, []);

  const value = useMemo(
    () => ({ store, plants, agents, ensure, setFilter, clearFilters, setDataMode, refresh, refreshedAt }),
    [store, plants, agents, ensure, setFilter, clearFilters, setDataMode, refresh, refreshedAt],
  );

  return <DashboardDataContext.Provider value={value}>{children}</DashboardDataContext.Provider>;
}
