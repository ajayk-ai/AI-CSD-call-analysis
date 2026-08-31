/**
 * View-layer types.
 *
 * The API's own response shapes live in `services/api.ts` alongside the client
 * that produces them; this file holds only what the UI itself defines.
 */

/** Keys accepted by `GET /api/dashboard/summary?range=`. */
export type TimeRangeKey = '1d' | '7d' | '1m' | '3m' | 'all';
