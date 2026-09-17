import { useState } from 'react';
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
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { sentimentMeta } from '../../data/presentation';
import { displayData, useDashboardSummary } from '../../state/dashboardContext';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './SentimentOverview.css';

const TOOLTIP_STYLE = {
  background: '#0f172a',
  border: '1px solid rgba(255,255,255,0.12)',
  borderRadius: 8,
  fontSize: 12,
};

export function SentimentOverview() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const state = useDashboardSummary(range);
  const data = displayData(state);

  const subtitle = data
    ? data.filters.agent
      ? `${data.filters.agent} — ${data.usable_calls} Usable Calls`
      : `Based on ${data.usable_calls} Usable Calls`
    : undefined;

  const monthlySentiment = data?.monthly_sentiment ?? [];
  const dailySentiment = data?.daily_sentiment ?? [];
  // Label every day when there are only a handful, otherwise every 5th - with
  // one or two analyzed days, filtering to multiples of 5 can hide the only
  // points on the chart.
  const dailyTicks =
    dailySentiment.length <= 8
      ? dailySentiment.map((d) => d.day)
      : dailySentiment.filter((d) => d.day === 1 || d.day % 5 === 0).map((d) => d.day);
  const hasTrend = monthlySentiment.length > 0 || dailySentiment.length > 0;

  return (
    <Card title="Overall Customer Sentiment" subtitle={subtitle} icon="💬">
      <TimeRangeFilter value={range} onChange={setRange} />
      {state.status === 'error' ? (
        <CardState kind="error" message={state.message} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : !hasTrend ? (
        <CardState
          kind="empty"
          message="No usable calls yet"
          hint="Recordings with no conversation (busy tone, no answer) are excluded from sentiment."
        />
      ) : (
        <div className="sentiment-trend">
          <div className="sentiment-trend__legend">
            {(['positive', 'neutral', 'negative'] as const).map((key) => (
              <span className="sentiment-trend__legend-item" key={key}>
                <span
                  className="sentiment-trend__swatch"
                  style={{ background: sentimentMeta(key).color }}
                />
                {sentimentMeta(key).emoji} {key.charAt(0).toUpperCase() + key.slice(1)}
              </span>
            ))}
          </div>
          <div className="sentiment-trend__split">
            <div className="sentiment-trend__panel">
              {monthlySentiment.length === 0 ? (
                <CardState kind="empty" message="No prior months analyzed yet" />
              ) : (
                <ResponsiveContainer width="100%" height={150}>
                  <BarChart data={monthlySentiment} margin={{ top: 16, right: 8, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" vertical={false} />
                    <XAxis
                      dataKey="month"
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={{ stroke: 'rgba(15,23,42,0.16)' }}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#f2f6fc' }} />
                    {(['positive', 'neutral', 'negative'] as const).map((key) => (
                      <Bar
                        key={key}
                        dataKey={key}
                        name={key.charAt(0).toUpperCase() + key.slice(1)}
                        fill={sentimentMeta(key).color}
                        radius={[4, 4, 0, 0]}
                        isAnimationActive={false}
                      />
                    ))}
                  </BarChart>
                </ResponsiveContainer>
              )}
              <p className="sentiment-trend__caption">Last 3 Months (Monthly Totals)</p>
            </div>
            <div className="sentiment-trend__divider" />
            <div className="sentiment-trend__panel">
              {dailySentiment.length === 0 ? (
                <CardState kind="empty" message="No calls this month" />
              ) : (
                <ResponsiveContainer width="100%" height={150}>
                  <LineChart data={dailySentiment} margin={{ top: 16, right: 12, left: -18, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(15,23,42,0.1)" vertical={false} />
                    <XAxis
                      dataKey="day"
                      ticks={dailyTicks}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={{ stroke: 'rgba(15,23,42,0.16)' }}
                      tickLine={false}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fill: 'var(--text-secondary)', fontSize: 10 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={TOOLTIP_STYLE}
                      labelStyle={{ color: '#f2f6fc' }}
                      labelFormatter={(day) => `Day ${day}`}
                    />
                    {(['positive', 'neutral', 'negative'] as const).map((key) => (
                      <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        name={key.charAt(0).toUpperCase() + key.slice(1)}
                        stroke={sentimentMeta(key).color}
                        strokeWidth={2}
                        dot={{ r: 2.5, fill: sentimentMeta(key).color }}
                        activeDot={{ r: 4 }}
                        isAnimationActive={false}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              )}
              <p className="sentiment-trend__caption">
                {data.current_month_label ? `${data.current_month_label} (Daily)` : 'Current Month (Daily)'}
              </p>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
