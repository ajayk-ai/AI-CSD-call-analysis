import type { TimeRangeKey } from '../../types/dashboard.types';
import './TimeRangeFilter.css';

interface TimeRangeFilterProps {
  value: TimeRangeKey;
  onChange: (range: TimeRangeKey) => void;
}

const RANGE_OPTIONS: { key: TimeRangeKey; label: string }[] = [
  { key: '1d', label: '1D' },
  { key: '7d', label: '1W' },
  { key: '1m', label: '1M' },
  { key: '3m', label: '3M' },
  { key: 'all', label: 'All' },
];

export function TimeRangeFilter({ value, onChange }: TimeRangeFilterProps) {
  return (
    <div className="time-range-filter" role="tablist" aria-label="Time range">
      {RANGE_OPTIONS.map((option) => (
        <button
          key={option.key}
          type="button"
          role="tab"
          aria-selected={value === option.key}
          className={`time-range-filter__btn ${value === option.key ? 'time-range-filter__btn--active' : ''}`}
          onClick={() => onChange(option.key)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
