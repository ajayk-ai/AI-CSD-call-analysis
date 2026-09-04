import type { CallFilters, DashboardFilters } from '../services/api';

/**
 * Turns the dashboard's active filters into the Calls page's filter shape, so
 * "Review calls" opens exactly the set a card's number was computed from —
 * not just the one dimension that card owns.
 *
 * `band` is the one dimension that doesn't survive the trip: it's a derived
 * bucket over whichever rating source the Satisfaction card currently shows
 * (ai vs. stated), and the Calls page's plain rating_min/max can't express
 * that choice too without knowing it. Dropping it is a silent narrowing
 * rather than a wrong result — the calls shown are still a superset of the
 * exact set, never a mismatched one.
 */
export function toCallFilters(
  filters: Partial<DashboardFilters>,
  overrides: CallFilters = {},
): CallFilters {
  const mapped: CallFilters = {};
  if (filters.agent) mapped.agent_name = filters.agent;
  if (filters.sentiment) mapped.sentiment = filters.sentiment;
  if (filters.quality) mapped.call_quality = filters.quality;
  if (filters.connection) mapped.connection_status = filters.connection;
  if (filters.adherence) mapped.script_adherence = filters.adherence;
  if (filters.category) mapped.category = filters.category;
  return { ...mapped, ...overrides };
}
