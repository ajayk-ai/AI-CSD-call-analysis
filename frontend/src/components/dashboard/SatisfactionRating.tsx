import { Card } from '../common/Card';
import type { SatisfactionRow } from '../../types/dashboard.types';
import './SatisfactionRating.css';

interface SatisfactionRatingProps {
  rows: SatisfactionRow[];
  usableCalls: number;
  averageRating: number;
}

export function SatisfactionRating({ rows, usableCalls, averageRating }: SatisfactionRatingProps) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  return (
    <Card
      title="Customer Satisfaction Rating"
      subtitle={`Based on ${usableCalls} Usable Calls`}
      icon="⭐"
      footer={
        <div className="satisfaction__avg">
          <span>⭐</span>
          <span>
            Average Rating (out of 10): <strong>{averageRating.toFixed(2)} / 10</strong>
          </span>
        </div>
      }
    >
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
          {rows.map((row) => (
            <tr key={row.band}>
              <td className="satisfaction-table__band">{row.band}</td>
              <td>
                <span className="satisfaction-table__pill" style={{ background: row.color }} />
                {row.description}
              </td>
              <td style={{ textAlign: 'right' }}>{row.count}</td>
              <td style={{ textAlign: 'right' }}>{row.percentage.toFixed(2)}%</td>
            </tr>
          ))}
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
    </Card>
  );
}
