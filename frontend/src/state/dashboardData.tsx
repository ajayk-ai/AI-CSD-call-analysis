import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { fetchDashboardPlants, fetchDashboardSummary } from '../services/api';
import type { TimeRangeKey } from '../types/dashboard.types';
import { cacheKey, DashboardDataContext, type Store } from './dashboardContext';

/**
 * One shared, (plant, range)-keyed cache of `GET /api/dashboard/summary`.
 *
 * Two cards carry their own independent time filter, and the rest of the page
 * reads the "all" summary; every card also shares one global plant filter.
 * Without a shared cache that's several components each firing their own
 * request for the same (plant, range) pair on mount. Entries are keyed by
 * `version:plant:range`; "Run Analysis" bumps the version, invalidating
 * everything at once — the pipeline moves every number on the page, so
 * refreshing panels piecemeal would leave the dashboard internally
 * inconsistent. Changing the plant filter does NOT bump the version — it's
 * just a different cache key, so switching back to a previous plant can serve
 * straight from cache.
 */
export function DashboardDataProvider({ children }: { children: ReactNode }) {
  const [store, setStore] = useState<Store>({ version: 0, plant: null, entries: {} });
  const [plants, setPlants] = useState<string[]>([]);
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);
  // Keys already dispatched. A ref rather than state, because starting a fetch
  // must not itself trigger a render — that would re-run the effect that
  // started it.
  const dispatched = useRef(new Set<string>());

  useEffect(() => {
    fetchDashboardPlants()
      .then((result) => setPlants(result.plants))
      // The filter just won't offer any options if this fails — every card
      // still renders its all-plants data, so there's nothing to surface.
      .catch(() => undefined);
  }, []);

  const ensure = useCallback((range: TimeRangeKey) => {
    setStore((current) => {
      const key = cacheKey(current.version, current.plant, range);
      if (dispatched.current.has(key)) return current;
      dispatched.current.add(key);

      fetchDashboardSummary(range, current.plant)
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
      const previous = current.entries[cacheKey(current.version - 1, current.plant, range)];
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

  const setPlant = useCallback((plant: string | null) => {
    // No cache invalidation needed: plant is part of the cache key, so this
    // is just a different set of entries, not a refresh of existing ones.
    setStore((current) => ({ ...current, plant }));
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
    () => ({ store, plants, ensure, setPlant, refresh, refreshedAt }),
    [store, plants, ensure, setPlant, refresh, refreshedAt],
  );

  return <DashboardDataContext.Provider value={value}>{children}</DashboardDataContext.Provider>;
}
