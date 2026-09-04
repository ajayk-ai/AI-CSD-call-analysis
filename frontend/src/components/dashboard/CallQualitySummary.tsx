import { qualityColor } from '../../data/presentation';
import { DonutBreakdownCard } from './DonutBreakdownCard';

/** Whether the RECORDING was clear enough to analyze — not whether a real
 *  conversation happened, which is CallConnectionSummary's question.
 *  Click a slice to scope the whole dashboard to calls of that quality. */
export function CallQualitySummary() {
  return (
    <DonutBreakdownCard
      title="Call Quality Summary"
      icon="📊"
      select={(data) => data.call_quality}
      total={(data) => data.analyzed_calls}
      totalNoun="Analyzed Calls"
      centerLabel="TOTAL CALLS"
      color={qualityColor}
      filterKey="quality"
      toReviewFilters={(key) => ({ call_quality: key })}
      emptyMessage="No analyzed calls in this range"
      emptyHint="Run an analysis, or widen the time range."
    />
  );
}
