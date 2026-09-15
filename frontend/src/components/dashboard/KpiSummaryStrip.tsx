import { InfoTip } from '../common/InfoTip';
import type { DashboardSummary } from '../../services/api';
import './KpiSummaryStrip.css';

interface KpiSummaryStripProps {
  data: DashboardSummary | null;
}

interface Trend {
  direction: 'up' | 'down';
  label: string;
  /** Whether "up" is the good direction for this metric — rating and volume
   *  read as good-when-up, but a metric like "issues raised" would not. */
  goodWhenUp: boolean;
}

/** Weighted by call_count so a 10/10 from one call doesn't count the same as
 *  a 10/10 average across forty — matches TrendComparison's own tooltip. */
function currentMonthFromDaily(data: DashboardSummary): { avg: number; calls: number } | null {
  if (data.daily_ratings.length === 0) return null;
  let ratingSum = 0;
  let calls = 0;
  for (const day of data.daily_ratings) {
    ratingSum += day.rating * day.call_count;
    calls += day.call_count;
  }
  return calls > 0 ? { avg: ratingSum / calls, calls } : null;
}

/** Below this many calls, the current month is too fresh (or too thin) for a
 *  month-to-date comparison to mean anything — early in a new month one call
 *  can swing an "average" wildly, and a volume comparison against a full
 *  prior month would read as a crash when it's really just "the month only
 *  just started." Suppressing the trend line here beats showing a real but
 *  misleading number. */
const MIN_CALLS_FOR_TREND = 8;

/** This-month-vs-last-month deltas — the only historical comparison the
 *  summary payload actually carries (`monthly_averages` + `daily_ratings`).
 *  Returns null rather than a guess when either side is missing or the
 *  current month is too thin to compare, so a KPI tile omits the trend line
 *  entirely instead of showing a misleading one. */
function ratingTrend(data: DashboardSummary): Trend | null {
  const current = currentMonthFromDaily(data);
  const previous = data.monthly_averages.at(-1);
  if (!current || !previous || current.calls < MIN_CALLS_FOR_TREND) return null;
  const delta = current.avg - previous.avg_rating;
  if (Math.abs(delta) < 0.05) return { direction: 'up', label: 'flat vs last month (MTD)', goodWhenUp: true };
  return {
    direction: delta > 0 ? 'up' : 'down',
    label: `${delta > 0 ? '+' : ''}${delta.toFixed(1)} vs last month (MTD)`,
    goodWhenUp: true,
  };
}

/** Deliberately NOT a volume trend: current month is always a partial
 *  month-to-date total, so comparing it against a full prior month's total
 *  reads as a dramatic drop every single month, regardless of actual pace —
 *  there's no fair like-for-like number to show here. */

function complianceStatus(pct: number): string {
  if (pct >= 90) return 'Excellent';
  if (pct >= 75) return 'Good';
  if (pct >= 50) return 'Needs attention';
  return 'Critical';
}

interface TileProps {
  label: string;
  tooltip?: string;
  value: string;
  caption: string;
  trend?: Trend | null;
}

function Tile({ label, tooltip, value, caption, trend }: TileProps) {
  return (
    <div className="kpi-tile">
      <div className="kpi-tile__label">
        {label}
        {tooltip && <InfoTip text={tooltip} />}
      </div>
      <div className="kpi-tile__value">{value}</div>
      <div className="kpi-tile__caption">
        {trend && (
          <span
            className={`kpi-tile__trend ${
              trend.direction === (trend.goodWhenUp ? 'up' : 'down')
                ? 'kpi-tile__trend--good'
                : 'kpi-tile__trend--bad'
            }`}
          >
            {trend.direction === 'up' ? '▲' : '▼'} {trend.label}
          </span>
        )}
        {!trend && caption}
      </div>
      {trend && <div className="kpi-tile__subcaption">{caption}</div>}
    </div>
  );
}

/**
 * "How are we performing?" — a glance-first strip above the detail cards.
 * Every number and trend here is read straight off the same summary payload
 * the rest of the dashboard already fetched (see DashboardSummary): no new
 * endpoint, and no delta is shown unless there's real prior-month data to
 * compare against (see ratingTrend/volumeTrend).
 */
export function KpiSummaryStrip({ data }: KpiSummaryStripProps) {
  if (!data) {
    return (
      <div className="kpi-strip kpi-strip--loading" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="kpi-tile kpi-tile--skeleton" />
        ))}
      </div>
    );
  }

  const followed = data.script_adherence.find((s) => s.key === 'followed');
  const compliancePct = followed?.percentage ?? null;
  const usableRate = data.reachable_calls > 0 ? (data.usable_calls / data.reachable_calls) * 100 : null;

  return (
    <div className="kpi-strip">
      <Tile
        label="Total Calls"
        tooltip="Every recording discovered in range, including ones not yet analyzed."
        value={data.total_calls.toLocaleString()}
        caption={`${data.analyzed_calls.toLocaleString()} analyzed`}
      />
      <Tile
        label="Average Rating"
        tooltip="AI-estimated satisfaction, 1-10, over usable calls only (see the Satisfaction card)."
        value={data.average_rating !== null ? `${data.average_rating.toFixed(2)} / 10` : '—'}
        caption={`${data.usable_calls.toLocaleString()} usable calls`}
        trend={ratingTrend(data)}
      />
      <Tile
        label="Reachable → Usable"
        tooltip="Of the calls that connected at all, the % that became a real conversation (excludes busy tones and voicemails)."
        value={usableRate !== null ? `${usableRate.toFixed(0)}%` : '—'}
        caption={`${data.usable_calls.toLocaleString()} of ${data.reachable_calls.toLocaleString()} reachable`}
      />
      <Tile
        label="Script Compliance"
        tooltip="Share of usable calls where the agent followed the standard call script."
        value={compliancePct !== null ? `${compliancePct.toFixed(0)}%` : '—'}
        caption={compliancePct !== null ? complianceStatus(compliancePct) : 'No data yet'}
      />
    </div>
  );
}
