import { scriptAdherenceColor } from '../../data/presentation';
import { DonutBreakdownCard } from './DonutBreakdownCard';

/** Whether agents followed the standard call script. Reads the dashboard's
 *  global agent filter (see AgentFilter / dashboardContext) the same way every
 *  other card does — pick an agent there (or from AgentPerformanceTable) and
 *  this recontextualizes to their own followed/partial/not-followed breakdown
 *  automatically, no local control needed here.
 *
 *  Clicking a slice works the other way round: it filters the whole dashboard
 *  to those calls, so "who and what is behind the not-followed ones" is one
 *  click away. */
export function AgentComplianceSummary() {
  return (
    <DonutBreakdownCard
      title="Agent Script Compliance"
      icon="📋"
      select={(data) => data.script_adherence}
      total={(data) => data.usable_calls}
      totalNoun="Usable Calls"
      centerLabel="USABLE CALLS"
      color={scriptAdherenceColor}
      filterKey="adherence"
      emptyMessage="No usable calls in this range"
      emptyHint="Run an analysis, or widen the time range."
    />
  );
}
