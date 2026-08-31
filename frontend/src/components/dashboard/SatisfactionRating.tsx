import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { bandMeta } from '../../data/presentation';
import type { DashboardSummary } from '../../services/api';
import './SatisfactionRating.css';

interface SatisfactionRatingProps {
  data: DashboardSummary | null;
  error?: string;
}

export function SatisfactionRating({ data, error }: SatisfactionRatingProps) {
  const rows = data?.satisfaction_bands ?? [];
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <Card
      title="Customer Satisfaction Rating"
      subtitle={data ? `Based on ${data.usable_calls} Usable Calls` : undefined}
      icon="⭐"
      footer={
        data && data.average_rating !== null ? (
          <div className="satisfaction__avg">
            <span>⭐</span>
            <span>
              Average Rating (out of 10): <strong>{data.average_rating.toFixed(2)} / 10</strong>
            </span>
          </div>
        ) : undefined
      }
    >
      {error ? (
        <CardState kind="error" message={error} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : rows.length === 0 ? (
        <CardState
          kind="empty"
          message="No ratings yet"
          hint="Only calls with an actual conversation are rated."
        />
      ) : (
        <table className="satisfaction-table">
          <thead>
            <tr>
              <th>Rating</th>
              <th>Customer Feedback</th>
              <th style={{ textAlign: 'right' }}>No. of Calls</th>
              <th style={{ textAlign: 'right' }}>%</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const meta = bandMeta(row.key);
              return (
                <tr key={row.key}>
                  <td className="satisfaction-table__band">{row.label}</td>
                  <td>
                    <span className="satisfaction-table__pill" style={{ background: meta.color }} />
                    {meta.tier}
                  </td>
                  <td style={{ textAlign: 'right' }}>{row.count}</td>
                  <td style={{ textAlign: 'right' }}>{row.percentage.toFixed(2)}%</td>
                </tr>
              );
            })}
          </tbody>
          <tfoot>
            <tr>
              <td className="satisfaction-table__total-label">Total</td>
              <td />
              <td style={{ textAlign: 'right', fontWeight: 700 }}>{total}</td>
              <td style={{ textAlign: 'right', fontWeight: 700 }}>100%</td>
            </tr>
          </tfoot>
        </table>
      )}
    </Card>
  );
}
