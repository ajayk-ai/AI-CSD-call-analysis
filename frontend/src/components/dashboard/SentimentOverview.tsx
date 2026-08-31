import { useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { DonutChart } from '../common/DonutChart';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { sentimentMeta } from '../../data/presentation';
import { displayData, useDashboardSummary } from '../../state/dashboardContext';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './SentimentOverview.css';

export function SentimentOverview() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const state = useDashboardSummary(range);
  const data = displayData(state);

  const slices = data?.sentiment ?? [];

  return (
    <Card
      title="Overall Customer Sentiment"
      subtitle={data ? `Based on ${data.usable_calls} Usable Calls` : undefined}
      icon="💬"
    >
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
                <li key={item.key} className="sentiment__legend-item">
                  <span className="sentiment__emoji">{meta.emoji}</span>
                  <div className="sentiment__legend-text">
                    <span className="sentiment__legend-label" style={{ color: meta.color }}>
                      {item.label}{' '}
                      <span className="sentiment__count">
                        {item.count} ({item.percentage.toFixed(2)}%)
                      </span>
                    </span>
                    <span className="sentiment__description">{meta.description}</span>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </Card>
  );
}
