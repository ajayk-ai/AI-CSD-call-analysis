import { useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { ClickableSlice, sliceTitle } from '../common/ClickableSlice';
import { DonutChart } from '../common/DonutChart';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import type { ApiSlice, CallFilters, DashboardSummary, FilterKey } from '../../services/api';
import { displayData, useDashboardSummary, useKpiFilter } from '../../state/dashboardContext';
import { toCallFilters } from '../../state/filterMapping';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './CallQualitySummary.css';

interface DonutBreakdownCardProps {
  title: string;
  icon: string;
  /** Which slice list to read off the summary, and what its denominator is. */
  select: (data: DashboardSummary) => ApiSlice[];
  total: (data: DashboardSummary) => number;
  /** Wording of the denominator, e.g. "Usable Calls". */
  totalNoun: string;
  centerLabel: string;
  color: (key: string) => string;
  /** The cross-filter dimension this card owns — clicking a slice sets it.
   *  The backend gives this card the breakdown computed WITHOUT this filter,
   *  so it keeps showing every slice and the selection stays changeable from
   *  here rather than collapsing to 100% of whatever was clicked. */
  filterKey: FilterKey;
  /** How a slice's key maps onto a Calls-page filter, e.g.
   *  `(key) => ({ connection_status: key })`. Omit for a card whose slices
   *  aren't reviewable on the Calls page (none currently, but this keeps the
   *  mapping local to the card that owns the dimension rather than guessed
   *  centrally). */
  toReviewFilters?: (key: string) => CallFilters;
  emptyMessage: string;
  emptyHint: string;
}

/**
 * The shared body of the three donut KPI cards (Call Quality, Call Connection
 * Quality, Agent Script Compliance).
 *
 * They were three copies of the same 60 lines over different fields; keeping
 * one implementation means the cross-filter interaction — the hover
 * affordance, the selected state, toggle-to-clear — can't drift between cards
 * that are supposed to feel identical.
 */
export function DonutBreakdownCard({
  title,
  icon,
  select,
  total,
  totalNoun,
  centerLabel,
  color,
  filterKey,
  toReviewFilters,
  emptyMessage,
  emptyHint,
}: DonutBreakdownCardProps) {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const state = useDashboardSummary(range);
  const data = displayData(state);
  const { toggle, isActive } = useKpiFilter(filterKey);

  const slices = data ? select(data) : [];
  const denominator = data ? total(data) : 0;
  const subtitle = data
    ? data.filters.agent
      ? `${data.filters.agent} — ${denominator} ${totalNoun}`
      : `Out of ${denominator} ${totalNoun}`
    : undefined;

  return (
    <Card title={title} subtitle={subtitle} icon={icon}>
      <TimeRangeFilter value={range} onChange={setRange} />
      {state.status === 'error' ? (
        <CardState kind="error" message={state.message} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : slices.length === 0 ? (
        <CardState kind="empty" message={emptyMessage} hint={emptyHint} />
      ) : (
        <div className="call-quality">
          <DonutChart
            data={slices.map((slice) => ({
              label: slice.label,
              value: slice.count,
              color: color(slice.key),
            }))}
            centerValue={String(denominator)}
            centerLabel={centerLabel}
            size={170}
          />
          <ul className="call-quality__legend">
            {slices.map((item) => (
              <li key={item.key}>
                <ClickableSlice
                  active={isActive(item.key)}
                  onClick={() => toggle(item.key)}
                  title={sliceTitle(isActive(item.key), `${item.label} calls`)}
                >
                  <span className="call-quality__legend-item">
                    <span className="call-quality__dot" style={{ background: color(item.key) }} />
                    <span className="call-quality__legend-text">
                      <span className="call-quality__legend-label">{item.label}</span>
                      <span className="call-quality__legend-value">
                        {item.count} ({item.percentage.toFixed(2)}%)
                      </span>
                    </span>
                  </span>
                </ClickableSlice>
                {toReviewFilters && (
                  <div className="call-quality__legend-review">
                    <OpenCallsButton
                      filters={toCallFilters(data?.filters ?? {}, toReviewFilters(item.key))}
                      label={`Review ${item.count}`}
                    />
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
