import { Card, type CardVariant } from '../common/Card';
import { CardState } from '../common/CardState';
import { RankedTable, type RankedTableColumn } from '../common/RankedTable';
import { iconForCategory } from '../../data/presentation';
import { useKpiFilter } from '../../state/dashboardContext';
import type { ApiSlice, DashboardSummary } from '../../services/api';

/**
 * Shared body of "Top Issue Analysis" and "Top Service / Machine Issues" —
 * same ranked table, different slice of the same payload. Kept in one place so
 * the ranking, totals and example column can't drift apart between the two.
 */

interface RankedIssuesCardProps {
  title: string;
  categoryHeader: string;
  totalLabel: string;
  icon: string;
  variant: CardVariant;
  rows: ApiSlice[];
  data: DashboardSummary | null;
  error?: string;
  emptyMessage: string;
  emptyHint?: string;
  fallbackIcon?: string;
}

export function RankedIssuesCard({
  title,
  categoryHeader,
  totalLabel,
  icon,
  variant,
  rows,
  data,
  error,
  emptyMessage,
  emptyHint,
  fallbackIcon,
}: RankedIssuesCardProps) {
  // All three issue tables share the one `category` dimension on purpose:
  // clicking "Spare Parts Pricing" anywhere should pull up everything true
  // about those calls, not just the table it was clicked in. The backend
  // matches across every mention type for the same reason.
  const { toggle, isActive } = useKpiFilter('category');
  const total = rows.reduce((sum, row) => sum + row.count, 0);

  // Rank is positional: the API already returns these largest-first.
  const ranked = rows.map((row, index) => ({ ...row, rank: index + 1 }));

  const columns: RankedTableColumn<(typeof ranked)[number]>[] = [
    {
      key: 'rank',
      header: 'Rank',
      width: '40px',
      render: (row) => <span className="ranked-table__rank">{row.rank}</span>,
    },
    {
      key: 'category',
      header: categoryHeader,
      width: '24%',
      render: (row) => (
        <span className="ranked-table__category">
          <span>{iconForCategory(row.key, fallbackIcon)}</span> {row.label}
        </span>
      ),
    },
    { key: 'count', header: 'No. of Calls', align: 'right', width: '70px', render: (row) => row.count },
    {
      key: 'pct',
      header: '%',
      align: 'right',
      width: '60px',
      render: (row) => `${row.percentage.toFixed(2)}%`,
    },
    {
      key: 'example',
      header: 'Example from Transcripts',
      render: (row) => (
        <>
          {row.example ? (
            <span className="ranked-table__example">"{row.example}"</span>
          ) : (
            <span className="ranked-table__example ranked-table__example--none">
              No quote captured
            </span>
          )}
          {row.tags.length > 0 && (
            <span className="ranked-table__tags">
              {row.tags.map((tag) => (
                <span key={tag} className="ranked-table__tag">
                  {tag}
                </span>
              ))}
            </span>
          )}
        </>
      ),
    },
  ];

  const subtitle = data
    ? data.filters.agent
      ? `${data.filters.agent} — ${data.usable_calls} Usable Calls`
      : `Based on ${data.usable_calls} Usable Calls`
    : undefined;

  return (
    <Card title={title} subtitle={subtitle} icon={icon} variant={variant}>
      {error ? (
        <CardState kind="error" message={error} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : ranked.length === 0 ? (
        <CardState kind="empty" message={emptyMessage} hint={emptyHint} />
      ) : (
        <RankedTable
          columns={columns}
          rows={ranked}
          getRowKey={(row) => row.key}
          onRowClick={(row) => toggle(row.key)}
          isRowActive={(row) => isActive(row.key)}
          rowTitle={(row) =>
            isActive(row.key)
              ? 'Clear this filter and show all calls again'
              : `Filter the whole dashboard to calls mentioning ${row.label}`
          }
          footer={[
            { content: totalLabel, colSpan: 2, align: 'left' },
            { content: total, align: 'right' },
            { content: '100%', align: 'right' },
            { content: '' },
          ]}
        />
      )}
    </Card>
  );
}
