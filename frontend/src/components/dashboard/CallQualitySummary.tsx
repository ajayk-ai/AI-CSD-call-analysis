import { useState } from 'react';
import { Card } from '../common/Card';
import { DonutChart } from '../common/DonutChart';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import type { CallQualityByRange, TimeRangeKey } from '../../types/dashboard.types';
import './CallQualitySummary.css';

interface CallQualitySummaryProps {
  byRange: CallQualityByRange;
}

export function CallQualitySummary({ byRange }: CallQualitySummaryProps) {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const snapshot = byRange[range];

  return (
    <Card title="Call Quality Summary" subtitle={`Out of ${snapshot.totalCalls} Calls`} icon="📊">
      <TimeRangeFilter value={range} onChange={setRange} />
      <div className="call-quality">
        <DonutChart
          data={snapshot.slices.map((d) => ({ label: d.label, value: d.count, color: d.color }))}
          centerValue={String(snapshot.totalCalls)}
          centerLabel="TOTAL CALLS"
          size={170}
        />
        <ul className="call-quality__legend">
          {snapshot.slices.map((item) => (
            <li key={item.label} className="call-quality__legend-item">
              <span className="call-quality__dot" style={{ background: item.color }} />
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
    </Card>
  );
}
