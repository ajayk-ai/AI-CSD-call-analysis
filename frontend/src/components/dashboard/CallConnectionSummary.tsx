import { connectionColor } from '../../data/presentation';
import { DonutBreakdownCard } from './DonutBreakdownCard';

/**
 * How the call itself went technically — good connection vs. a network drop,
 * no-answer, or dead air — independent of recording clarity (that's
 * CallQualitySummary). Scoped to usable calls, so it answers the narrow
 * question worth asking: of the calls we could actually use, how many still
 * hit a network problem?
 *
 * Click a slice to pull the rest of the dashboard onto those calls — e.g.
 * "what do the mid-call drops have in common?"
 */
export function CallConnectionSummary() {
  return (
    <DonutBreakdownCard
      title="Call Connection Quality"
      icon="📶"
      select={(data) => data.connection_status}
      total={(data) => data.usable_calls}
      totalNoun="Usable Calls"
      centerLabel="USABLE CALLS"
      color={connectionColor}
      filterKey="connection"
      emptyMessage="No usable calls in this range"
      emptyHint="Run an analysis, or widen the time range."
    />
  );
}
