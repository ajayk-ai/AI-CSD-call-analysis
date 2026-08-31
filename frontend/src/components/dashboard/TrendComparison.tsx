import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import type { DashboardSummary } from '../../services/api';
import './TrendComparison.css';

interface TrendComparisonProps {
  data: DashboardSummary | null;
  error?: string;
}

const TOOLTIP_STYLE = {
  background: '#0f2138',
  border: '1px solid rgba(148,180,226,0.3)',
  borderRadius: 8,
  fontSize: 12,
};

/**
 * Shows the call count behind each point, so a 10.0 drawn from a single call
 * doesn't read like a 10.0 drawn from forty. Params are `unknown` because
 * recharts' Formatter signature varies by chart type; the payload shape is
 * ours either way.
 */
function ratingTooltipFormatter(value: unknown, _name: unknown, item: unknown): [string, string] {
  const count = (item as { payload?: { call_count?: number } })?.payload?.call_count ?? 0;
  return [`${value} / 10 (${count} call${count === 1 ? '' : 's'})`, 'Average rating'];
}

export function TrendComparison({ data, error }: TrendComparisonProps) {
  const monthlyAverages = data?.monthly_averages ?? [];
  const dailyRatings = data?.daily_ratings ?? [];

  // Label every day when there are only a handful, otherwise every 5th - with
  // one or two analyzed days, filtering to multiples of 5 can hide the only
  // points on the chart.
  const dailyTicks =
    dailyRatings.length <= 8
      ? dailyRatings.map((d) => d.day)
      : dailyRatings.filter((d) => d.day === 1 || d.day % 5 === 0).map((d) => d.day);

  return (
    <Card
      title="Last 3 Months Average vs Current Month Trend"
      subtitle={data?.current_month_label ? `Current month: ${data.current_month_label}` : undefined}
      icon="📈"
    >
      {error ? (
        <CardState kind="error" message={error} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : dailyRatings.length === 0 && monthlyAverages.length === 0 ? (
        <CardState
          kind="empty"
          message="No rated calls yet"
          hint="The trend fills in as analyzed calls accumulate across days and months."
        />
      ) : (
        <>
          <div className="trend-legend">
            <span className="trend-legend__item">
              <span className="trend-legend__swatch trend-legend__swatch--bar" /> Last 3 Months
              Average Rating
            </span>
            <span className="trend-legend__item">
              <span className="trend-legend__swatch trend-legend__swatch--line" /> Current Month
              Daily Rating
            </span>
          </div>
          <div className="trend-split">
            <div className="trend-split__panel">
              {monthlyAverages.length === 0 ? (
                // Deliberately not a zeroed bar chart: a bar at 0 reads as
                // "everyone was furious", not "we have no history yet".
                <CardState kind="empty" message="No prior months analyzed yet" />
              ) : (
                <ResponsiveContainer width="100%" height={160}>
                  <BarChart data={monthlyAverages} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,180,226,0.12)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={{ stroke: 'rgba(148,180,226,0.2)' }}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 10]}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      labelStyle={{ color: '#f2f6fc' }}
                      formatter={ratingTooltipFormatter}
                    />
                    <Bar
                      dataKey="avg_rating"
                      fill="#3b82f6"
                      radius={[6, 6, 0, 0]}
                      label={{ position: 'top', fill: '#f2f6fc', fontSize: 11, fontWeight: 700 }}
                      isAnimationActive={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              )}
              <p className="trend-split__caption">Last 3 Months (Monthly Avg)</p>
            </div>
            <div className="trend-split__divider" />
            <div className="trend-split__panel">
              {dailyRatings.length === 0 ? (
                <CardState kind="empty" message="No calls this month" />
              ) : (
                <ResponsiveContainer width="100%" height={160}>
                  <LineChart data={dailyRatings} margin={{ top: 16, right: 12, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,180,226,0.12)" vertical={false} />
                    <XAxis
                      dataKey="day"
                      ticks={dailyTicks}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={{ stroke: 'rgba(148,180,226,0.2)' }}
                      tickLine={false}
                    />
                    <YAxis
                      domain={[0, 10]}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      labelStyle={{ color: '#f2f6fc' }}
                      labelFormatter={(day) => `Day ${day}`}
                      formatter={ratingTooltipFormatter}
                    />
                    <Line
                      type="monotone"
                      dataKey="rating"
                      stroke="#2ecc71"
                      strokeWidth={2}
                      dot={{ r: 2.5, fill: '#2ecc71' }}
                      activeDot={{ r: 4 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
              <p className="trend-split__caption">
                {data.current_month_label ? `${data.current_month_label} (Daily)` : 'Current Month (Daily)'}
              </p>
            </div>
          </div>
        </>
      )}
    </Card>
  );
}
