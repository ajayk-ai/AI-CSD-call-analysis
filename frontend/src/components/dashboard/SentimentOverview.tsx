import { useState } from 'react';
import { Card } from '../common/Card';
import { DonutChart } from '../common/DonutChart';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import type { SentimentByRange, TimeRangeKey } from '../../types/dashboard.types';
import './SentimentOverview.css';

interface SentimentOverviewProps {
  byRange: SentimentByRange;
}

export function SentimentOverview({ byRange }: SentimentOverviewProps) {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const snapshot = byRange[range];

  return (
    <Card title="Overall Customer Sentiment" subtitle={`Based on ${snapshot.usableCalls} Usable Calls`} icon="💬">
      <TimeRangeFilter value={range} onChange={setRange} />
      <div className="sentiment">
        <DonutChart
          data={snapshot.slices.map((d) => ({ label: d.label, value: d.count, color: d.color }))}
          size={170}
        />
        <ul className="sentiment__legend">
          {snapshot.slices.map((item) => (
            <li key={item.label} className="sentiment__legend-item">
              <span className="sentiment__emoji">{item.emoji}</span>
              <div className="sentiment__legend-text">
                <span className="sentiment__legend-label" style={{ color: item.color }}>
                  {item.label} <span className="sentiment__count">{item.count} ({item.percentage.toFixed(2)}%)</span>
                </span>
                <span className="sentiment__description">{item.description}</span>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </Card>
  );
}
