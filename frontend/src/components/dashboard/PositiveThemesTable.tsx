import { Card } from '../common/Card';
import { RankedTable, type RankedTableColumn } from '../common/RankedTable';
import type { PositiveThemeRow } from '../../types/dashboard.types';

interface PositiveThemesTableProps {
  rows: PositiveThemeRow[];
  usableCalls: number;
}

export function PositiveThemesTable({ rows, usableCalls }: PositiveThemesTableProps) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  const columns: RankedTableColumn<PositiveThemeRow>[] = [
    { key: 'rank', header: 'Rank', width: '40px', render: (row) => <span className="ranked-table__rank">{row.rank}</span> },
    {
      key: 'theme',
      header: 'Positive Theme',
      render: (row) => (
        <span className="ranked-table__category">
          <span style={{ color: 'var(--color-good)' }}>{row.icon}</span> {row.theme}
        </span>
      ),
    },
    { key: 'count', header: 'No. of Calls', align: 'right', width: '90px', render: (row) => row.count },
    { key: 'pct', header: '%', align: 'right', width: '70px', render: (row) => `${row.percentage.toFixed(2)}%` },
  ];

  return (
    <Card
      title="Positive Feedback Themes"
      subtitle={`Based on ${usableCalls} Usable Calls`}
      icon="👍"
      variant="teal"
    >
      <RankedTable
        columns={columns}
        rows={rows}
        getRowKey={(row) => row.rank}
        footer={[
          { content: 'Total Positive Mentions', colSpan: 2 },
          { content: total, align: 'right' },
          { content: '100%', align: 'right' },
        ]}
      />
    </Card>
  );
}
