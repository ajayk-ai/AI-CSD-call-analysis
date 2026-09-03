import { useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { ClickableSlice, sliceTitle } from '../common/ClickableSlice';
import { DonutChart } from '../common/DonutChart';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { sentimentMeta } from '../../data/presentation';
import { displayData, useDashboardSummary, useKpiFilter } from '../../state/dashboardContext';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './SentimentOverview.css';

export function SentimentOverview() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const state = useDashboardSummary(range);
  const data = displayData(state);
  // This card owns the `sentiment` dimension: the backend deliberately gives
  // it the breakdown computed WITHOUT its own filter, so it keeps showing all
  // three moods and the selection can be changed from here.
  const { toggle, isActive } = useKpiFilter('sentiment');

  const slices = data?.sentiment ?? [];
  const subtitle = data
    ? data.filters.agent
      ? `${data.filters.agent} — ${data.usable_calls} Usable Calls`
      : `Based on ${data.usable_calls} Usable Calls`
    : undefined;

  return (
    <Card title="Overall Customer Sentiment" subtitle={subtitle} icon="💬">
      <TimeRangeFilter value={range} onChange={setRange} />
      {state.status === 'error' ? (
        <CardState kind="error" message={state.message} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : slices.length === 0 ? (
        <CardState
          kind="empty"
          message="No usable calls in this range"
          hint="Recordings with no conversation (busy tone, no answer) are excluded from sentiment."
        />
      ) : (
        <div className="sentiment">
          <DonutChart
            data={slices.map((slice) => ({
              label: slice.label,
              value: slice.count,
              color: sentimentMeta(slice.key).color,
            }))}
            size={170}
          />
          <ul className="sentiment__legend">
            {slices.map((item) => {
              const meta = sentimentMeta(item.key);
              return (
                <li key={item.key}>
                  <ClickableSlice
                    active={isActive(item.key)}
                    onClick={() => toggle(item.key)}
                    title={sliceTitle(isActive(item.key), `${item.label} calls`)}
                  >
                    <span className="sentiment__legend-item">
                      <span className="sentiment__emoji">{meta.emoji}</span>
                      <span className="sentiment__legend-text">
                        <span className="sentiment__legend-label" style={{ color: meta.color }}>
                          {item.label}{' '}
                          <span className="sentiment__count">
                            {item.count} ({item.percentage.toFixed(2)}%)
                          </span>
                        </span>
                        <span className="sentiment__description">{meta.description}</span>
                      </span>
                    </span>
                  </ClickableSlice>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
