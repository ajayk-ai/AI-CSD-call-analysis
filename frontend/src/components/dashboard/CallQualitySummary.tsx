import { useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { DonutChart } from '../common/DonutChart';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { qualityColor } from '../../data/presentation';
import { displayData, useDashboardSummary } from '../../state/dashboardContext';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './CallQualitySummary.css';

export function CallQualitySummary() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const state = useDashboardSummary(range);
  const data = displayData(state);

  const slices = data?.call_quality ?? [];
  const analyzed = data?.analyzed_calls ?? 0;

  return (
    <Card
      title="Call Quality Summary"
      subtitle={data ? `Out of ${analyzed} Analyzed Calls` : undefined}
      icon="📊"
    >
      <TimeRangeFilter value={range} onChange={setRange} />
      {state.status === 'error' ? (
        <CardState kind="error" message={state.message} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : slices.length === 0 ? (
        <CardState
          kind="empty"
          message="No analyzed calls in this range"
          hint="Run an analysis, or widen the time range."
        />
      ) : (
        <div className="call-quality">
          <DonutChart
            data={slices.map((slice) => ({
              label: slice.label,
              value: slice.count,
              color: qualityColor(slice.key),
            }))}
            centerValue={String(analyzed)}
            centerLabel="TOTAL CALLS"
            size={170}
          />
          <ul className="call-quality__legend">
            {slices.map((item) => (
              <li key={item.key} className="call-quality__legend-item">
                <span className="call-quality__dot" style={{ background: qualityColor(item.key) }} />
                <span className="call-quality__legend-text">
                  <span className="call-quality__legend-label">{item.label}</span>
                  <span className="call-quality__legend-value">
                    {item.count} ({item.percentage.toFixed(2)}%)
                  </span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}
