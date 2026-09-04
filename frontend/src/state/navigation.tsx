import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import type { CallFilters } from '../services/api';
import type { TabKey } from '../components/layout/TabNav';

/**
 * Moving between tabs with a filter in hand.
 *
 * A dashboard number is only half an answer: "9 calls complained about
 * follow-up" invites the immediate question "which nine?". Without this the
 * only way to find out is to switch to Calls and rebuild the filter by hand
 * from memory, which in practice means nobody checks — and an unverifiable
 * number is one people stop trusting.
 *
 * So the issue tables, the connection card and the Key Insights tiles hand a
 * `CallFilters` to `openCalls()`, which switches tab and seeds the Calls
 * page's filter bar with it. The filter is ordinary and visible once you land,
 * so it can be widened or cleared from there like any other.
 */
interface NavigationValue {
  tab: TabKey;
  setTab: (tab: TabKey) => void;
  /** Filters to seed the Calls page with on its next mount; null = leave as-is. */
  pendingCallFilters: CallFilters | null;
  /** Jump to the Calls tab showing exactly these calls. */
  openCalls: (filters: CallFilters) => void;
  /** Called by the Calls page once it has consumed the seed. */
  consumeCallFilters: () => void;
}

const NavigationContext = createContext<NavigationValue | null>(null);

export function NavigationProvider({ children }: { children: ReactNode }) {
  const [tab, setTab] = useState<TabKey>('dashboard');
  const [pendingCallFilters, setPendingCallFilters] = useState<CallFilters | null>(null);

  const openCalls = useCallback((filters: CallFilters) => {
    setPendingCallFilters(filters);
    setTab('calls');
  }, []);

  const consumeCallFilters = useCallback(() => setPendingCallFilters(null), []);

  const value = useMemo(
    () => ({ tab, setTab, pendingCallFilters, openCalls, consumeCallFilters }),
    [tab, pendingCallFilters, openCalls, consumeCallFilters],
  );

  return <NavigationContext.Provider value={value}>{children}</NavigationContext.Provider>;
}

export function useNavigation(): NavigationValue {
  const context = useContext(NavigationContext);
  if (!context) {
    throw new Error('useNavigation must be used inside <NavigationProvider>');
  }
  return context;
}
