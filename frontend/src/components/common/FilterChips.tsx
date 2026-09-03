import { useDashboardFilters } from '../../state/dashboardContext';
import type { DashboardFilters } from '../../services/api';
import './FilterChips.css';

/** How each dimension reads in a chip, and how its raw value is worded.
 *
 *  Values come off the wire as enum strings ("dropped_during_call"), which is
 *  right for the API and wrong for a person — so each dimension says how to
 *  present itself rather than the chip row guessing.
 */
const CHIP_META: Record<
  keyof DashboardFilters,
  { label: string; format?: (value: string) => string }
> = {
  plant: { label: 'Plant' },
  agent: { label: 'Agent' },
  sentiment: { label: 'Sentiment', format: titleCase },
  connection: { label: 'Connection', format: titleCase },
  band: { label: 'Satisfaction', format: (v) => (v === 'Not Given' ? v : `${v} / 10`) },
  quality: { label: 'Call Quality', format: titleCase },
  adherence: { label: 'Script', format: titleCase },
  category: { label: 'Category' },
};

const ORDER = Object.keys(CHIP_META) as (keyof DashboardFilters)[];

function titleCase(value: string): string {
  return value
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
}

/**
 * The row of removable chips showing what the dashboard is currently filtered
 * by.
 *
 * This is the half of cross-filtering that makes it safe to use: clicking into
 * a slice is discoverable, but clicking *out* of one is not — especially after
 * two or three clicks, when it's no longer obvious which cards are narrowed or
 * why the numbers moved. Every active filter is therefore always visible here
 * and always one click from gone.
 *
 * Renders nothing when nothing is filtered, so the dashboard doesn't carry an
 * empty bar around in its default state.
 */
export function FilterChips() {
  const { filters, setFilter, clearFilters } = useDashboardFilters();
  const active = ORDER.filter((key) => filters[key]);

  if (active.length === 0) return null;

  return (
    <div className="filter-chips" role="status">
      <span className="filter-chips__lead">Filtered by</span>
      {active.map((key) => {
        const meta = CHIP_META[key];
        const value = filters[key] as string;
        return (
          <span key={key} className="filter-chips__chip">
            <span className="filter-chips__key">{meta.label}</span>
            <span className="filter-chips__value">{meta.format ? meta.format(value) : value}</span>
            <button
              type="button"
              className="filter-chips__remove"
              onClick={() => setFilter(key, null)}
              aria-label={`Remove the ${meta.label} filter`}
              title={`Remove the ${meta.label} filter`}
            >
              ×
            </button>
          </span>
        );
      })}
      {active.length > 1 && (
        <button type="button" className="filter-chips__clear" onClick={clearFilters}>
          Clear all
        </button>
      )}
    </div>
  );
}
