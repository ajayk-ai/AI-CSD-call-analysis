import { Card } from '../common/Card';
import { RankedTable, type RankedTableColumn } from '../common/RankedTable';
import type { RankedIssueRow } from '../../types/dashboard.types';

interface ServiceIssuesTableProps {
  rows: RankedIssueRow[];
  usableCalls: number;
}

export function ServiceIssuesTable({ rows, usableCalls }: ServiceIssuesTableProps) {
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  const columns: RankedTableColumn<RankedIssueRow>[] = [
    { key: 'rank', header: 'Rank', width: '40px', render: (row) => <span className="ranked-table__rank">{row.rank}</span> },
    {
      key: 'category',
      header: 'Service / Machine Issue',
      width: '24%',
      render: (row) => (
        <span className="ranked-table__category">
          <span>{row.icon}</span> {row.category}
        </span>
      ),
    },
    { key: 'count', header: 'No. of Calls', align: 'right', width: '70px', render: (row) => row.count },
    { key: 'pct', header: '%', align: 'right', width: '60px', render: (row) => `${row.percentage.toFixed(2)}%` },
    {
      key: 'example',
      header: 'Example from Transcripts',
      render: (row) => <span className="ranked-table__example">{row.example}</span>,
    },
  ];

  return (
    <Card
      title="Top Service / Machine Issues Reported"
      subtitle={`Based on ${usableCalls} Usable Calls`}
      icon="🛠️"
      variant="blue"
    >
      <RankedTable
        columns={columns}
        rows={rows}
        getRowKey={(row) => row.rank}
        footer={[
          { content: 'Total Issue Mentions', colSpan: 2 },
          { content: total, align: 'right' },
          { content: '100%', align: 'right' },
          { content: '' },
        ]}
      />
    </Card>
  );
}
