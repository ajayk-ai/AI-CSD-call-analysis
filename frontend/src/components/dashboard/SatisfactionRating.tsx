import { useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { bandMeta } from '../../data/presentation';
import { displayData, useDashboardSummary, useKpiFilter } from '../../state/dashboardContext';
import { toCallFilters } from '../../state/filterMapping';
import type { CallFilters, RatingSource } from '../../services/api';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './SatisfactionRating.css';

const SOURCE_OPTIONS: { key: RatingSource; label: string }[] = [
  { key: 'ai', label: 'AI Estimated' },
  { key: 'stated', label: 'Customer Stated' },
];

/** `/api/calls`'s rating_min/max filter the AI estimate column only, so a
 *  direct "review these calls" link is only exact under the AI source — under
 *  "Customer Stated" it would silently filter on the wrong number. */
function bandToCallFilters(band: string): CallFilters | null {
  if (band === 'Not Given') return null;
  // conversations_only: a rating band is only meaningful over calls where a
  // customer actually spoke — a busy tone's placeholder rating of 5 would
  // otherwise get counted into "1 - 7" by coincidence, not by any real
  // dissatisfaction.
  if (band === '9 - 10') return { rating_min: 9, conversations_only: true };
  if (band === '8') return { rating_min: 8, rating_max: 8, conversations_only: true };
  return { rating_max: 7, conversations_only: true };
}

export function SatisfactionRating({ range = 'all' }: { range?: TimeRangeKey }) {
  const [source, setSource] = useState<RatingSource>('ai');
  const state = useDashboardSummary(range, source);
  const data = displayData(state);
  const error = state.status === 'error' ? state.message : undefined;
  // Band rows are clickable: this card owns the `band` dimension, so it keeps
  // showing every band while the rest of the dashboard narrows to the one
  // picked. Note the band is interpreted against whichever rating source is
  // selected here — filtering by "1 - 7" under "Customer Stated" means calls
  // where the CUSTOMER said 7 or less, not where the model estimated it.
  const { toggle, isActive } = useKpiFilter('band');

  const rows = data?.satisfaction_bands ?? [];
  const total = rows.reduce((sum, row) => sum + row.count, 0);
  const subtitle = data
    ? data.filters.agent
      ? `${data.filters.agent} — ${data.usable_calls} Usable Calls`
      : `Based on ${data.usable_calls} Usable Calls`
    : undefined;

  return (
    <Card
      title="Customer Satisfaction Rating"
      subtitle={subtitle}
      icon="⭐"
      footer={
        <div className="satisfaction__avg">
          <span>⭐</span>
          <span>
            Average Rating (out of 10):{' '}
            <strong>{data && data.average_rating !== null ? `${data.average_rating.toFixed(2)} / 10` : '—'}</strong>
          </span>
        </div>
      }
    >
      <div className="satisfaction__source" role="tablist" aria-label="Rating source">
        {SOURCE_OPTIONS.map((option) => (
          <button
            key={option.key}
            type="button"
            role="tab"
            aria-selected={source === option.key}
            className={`satisfaction__source-btn ${source === option.key ? 'satisfaction__source-btn--active' : ''}`}
            onClick={() => setSource(option.key)}
          >
            {option.label}
          </button>
        ))}
      </div>
      {error ? (
        <CardState kind="error" message={error} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : rows.length === 0 ? (
        <CardState
          kind="empty"
          message="No ratings yet"
          hint="Only calls with an actual conversation are rated."
        />
      ) : (
        <table className="satisfaction-table">
          <thead>
            <tr>
              <th>Rating</th>
              <th>Customer Feedback</th>
              <th style={{ textAlign: 'right' }}>No. of Calls</th>
              <th style={{ textAlign: 'right' }}>%</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const isNotGiven = row.key === 'Not Given';
              const meta = bandMeta(row.key);
              const active = isActive(row.key);
              return (
                <tr
                  key={row.key}
                  className={[
                    isNotGiven ? 'satisfaction-table__row--muted' : '',
                    'satisfaction-table__row--clickable',
                    active ? 'satisfaction-table__row--active' : '',
                  ]
                    .filter(Boolean)
                    .join(' ')}
                  onClick={() => toggle(row.key)}
                  title={
                    active
                      ? 'Clear this filter and show all calls again'
                      : `Filter the whole dashboard to calls rated ${row.label}`
                  }
                >
                  <td className="satisfaction-table__band">{row.label}</td>
                  <td>
                    {!isNotGiven && (
                      <span className="satisfaction-table__pill" style={{ background: meta.color }} />
                    )}
                    {isNotGiven ? 'Customer did not state a rating' : meta.tier}
                  </td>
                  <td style={{ textAlign: 'right' }}>{row.count}</td>
                  <td style={{ textAlign: 'right' }}>{row.percentage.toFixed(2)}%</td>
                  <td onClick={(e) => e.stopPropagation()}>
                    {source === 'ai' &&
                      bandToCallFilters(row.key) &&
                      row.count > 0 && (
                        <OpenCallsButton
                          filters={toCallFilters(data?.filters ?? {}, bandToCallFilters(row.key) ?? {})}
                        />
                      )}
                  </td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td className="satisfaction-table__total-label">Total</td>
              <td />
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{total}</td>
              <td style={{ textAlign: 'right', fontWeight: 700 }}>100%</td>
              <td />
            </tr>
          </tfoot>
        </table>
      )}
    </Card>
  );
}
