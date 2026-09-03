/**
 * Presentation metadata for values the API returns.
 *
 * The backend owns the numbers and the wording; this file owns how they look.
 * Everything keys off the API's stable `key` field (an enum value, or a
 * category name) rather than the display label, so re-wording a label can't
 * silently drop a color.
 *
 * Categories are NOT a fixed list — the model grows the taxonomy as new kinds
 * of case arrive (see backend/app/services/category_service.py) — so issue
 * icons are resolved by keyword with a fallback, never by exact lookup.
 */

export const QUALITY_COLORS: Record<string, string> = {
  good_clear: 'var(--color-good)',
  partial_usable: 'var(--color-warning)',
  rejected_corrupted: 'var(--color-bad)',
};

export const CONNECTION_COLORS: Record<string, string> = {
  connected: 'var(--color-good)',
  dropped_during_call: 'var(--color-warning)',
  dropped_at_greeting: 'var(--color-warning)',
  no_answer_busy: 'var(--color-bad)',
  voicemail_ivr_only: 'var(--color-bad)',
  silent_dead_air: 'var(--color-bad)',
};

export const SCRIPT_ADHERENCE_COLORS: Record<string, string> = {
  followed: 'var(--color-good)',
  partial: 'var(--color-warning)',
  not_followed: 'var(--color-bad)',
};

export interface SentimentMeta {
  emoji: string;
  color: string;
  description: string;
}

export const SENTIMENT_META: Record<string, SentimentMeta> = {
  positive: {
    emoji: '🙂',
    color: 'var(--color-good)',
    description: 'Satisfied with service, technician behavior and dealer support',
  },
  neutral: {
    emoji: '😐',
    color: 'var(--color-warning)',
    description: 'Mixed experience, some issues but manageable',
  },
  negative: {
    emoji: '☹️',
    color: 'var(--color-bad)',
    description: 'Very dissatisfied mainly due to response time & resolution',
  },
};

export interface BandMeta {
  tier: string;
  color: string;
}

/** Banding matches the backend's `_satisfaction_band`: 9-10 satisfied, 8
 *  borderline/"on the fence", 1-7 not satisfied. */
export const SATISFACTION_META: Record<string, BandMeta> = {
  '9 - 10': { tier: 'Satisfied', color: 'var(--color-good)' },
  '8': { tier: 'Borderline', color: 'var(--color-warning)' },
  '1 - 7': { tier: 'Not Satisfied', color: 'var(--color-bad)' },
};

const DEFAULT_COLOR = 'var(--color-info)';

export function qualityColor(key: string): string {
  return QUALITY_COLORS[key] ?? DEFAULT_COLOR;
}

export function connectionColor(key: string): string {
  return CONNECTION_COLORS[key] ?? DEFAULT_COLOR;
}

export function scriptAdherenceColor(key: string): string {
  return SCRIPT_ADHERENCE_COLORS[key] ?? DEFAULT_COLOR;
}

export function sentimentMeta(key: string): SentimentMeta {
  return SENTIMENT_META[key] ?? { emoji: '•', color: DEFAULT_COLOR, description: '' };
}

export function bandMeta(key: string): BandMeta {
  return SATISFACTION_META[key] ?? { tier: key, color: DEFAULT_COLOR };
}

/**
 * Keyword -> icon, first match wins. Ordered most-specific first: "GPS" has to
 * be tested before "electrical" so "Electrical / Wiring / GPS Issues" doesn't
 * take the plug icon by accident of ordering.
 */
const CATEGORY_ICONS: [RegExp, string][] = [
  [/hydraulic/i, '🧰'],
  [/oil|leak|lubricat/i, '🛢️'],
  [/pipe|hose|burst/i, '🚿'],
  [/transmission|gear|clutch/i, '⚙️'],
  [/\bac\b|cool|temperature/i, '❄️'],
  [/gps|telemat|track/i, '📡'],
  [/electric|wiring|battery|charg/i, '🔌'],
  [/engine|power|starter/i, '🏎️'],
  [/spare|part/i, '⚙️'],
  [/delay|slow|time|wait|respons/i, '⏱️'],
  [/repeat|recurr|again|unresolved|not resolved/i, '🔁'],
  [/follow.?up|update|communicat|inform/i, '📞'],
  [/install|deliver|dispatch/i, '🚚'],
  [/technician|engineer|staff|behav|courte/i, '🧑‍🔧'],
  [/dealer|support|service centre|service center/i, '🤝'],
  [/resolv|fixed|solution/i, '✅'],
  [/satisf|trust|happy|praise|apprecia/i, '⭐'],
  [/cost|price|bill|charge|payment/i, '💰'],
  [/warrant|claim/i, '📄'],
];

export function iconForCategory(category: string, fallback = '🔧'): string {
  for (const [pattern, icon] of CATEGORY_ICONS) {
    if (pattern.test(category)) return icon;
  }
  return fallback;
}
