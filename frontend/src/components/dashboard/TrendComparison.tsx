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
import type { DailyRating, MonthlyAverage } from '../../types/dashboard.types';
import './TrendComparison.css';

interface TrendComparisonProps {
  monthlyAverages: MonthlyAverage[];
  dailyRatings: DailyRating[];
}

export function TrendComparison({ monthlyAverages, dailyRatings }: TrendComparisonProps) {
  const dailyTicks = dailyRatings
    .filter((d) => d.day === 1 || d.day % 5 === 0)
    .map((d) => d.day);

  return (
    <Card title="Last 3 Months Average vs Current Month Trend" icon="📈">
      <div className="trend-legend">
        <span className="trend-legend__item">
          <span className="trend-legend__swatch trend-legend__swatch--bar" /> Last 3 Months Average Rating
        </span>
        <span className="trend-legend__item">
          <span className="trend-legend__swatch trend-legend__swatch--line" /> Current Month Daily Rating
        </span>
      </div>
      <div className="trend-split">
        <div className="trend-split__panel">
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
                contentStyle={{ background: '#0f2138', border: '1px solid rgba(148,180,226,0.3)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#f2f6fc' }}
              />
              <Bar
                dataKey="avgRating"
                fill="#3b82f6"
                radius={[6, 6, 0, 0]}
                label={{ position: 'top', fill: '#f2f6fc', fontSize: 11, fontWeight: 700 }}
                isAnimationActive={false}
              />
            </BarChart>
          </ResponsiveContainer>
          <p className="trend-split__caption">Last 3 Months (Monthly Avg)</p>
        </div>
        <div className="trend-split__divider" />
        <div className="trend-split__panel">
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
                contentStyle={{ background: '#0f2138', border: '1px solid rgba(148,180,226,0.3)', borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: '#f2f6fc' }}
                labelFormatter={(day) => `Day ${day}`}
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
          <p className="trend-split__caption">Current Month (Daily)</p>
        </div>
      </div>
    </Card>
  );
}
