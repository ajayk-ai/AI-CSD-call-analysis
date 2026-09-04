import { Card, type CardVariant } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { RankedTable, type RankedTableColumn } from '../common/RankedTable';
import { iconForCategory } from '../../data/presentation';
import { useKpiFilter } from '../../state/dashboardContext';
import { useNavigation } from '../../state/navigation';
import { toCallFilters } from '../../state/filterMapping';
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
  const { openCalls } = useNavigation();
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
      header: '% of Usable',
      align: 'right',
      width: '75px',
      render: (row) => `${row.percentage.toFixed(1)}%`,
    },
    {
      key: 'split',
      header: 'Praise vs. Problem',
      align: 'right',
      width: '110px',
      render: (row) =>
        row.negative_share !== null ? (
          <span className="ranked-table__split" title={`Praised on ${row.positive_calls}, a problem on ${row.negative_calls}`}>
            <span className="ranked-table__split-neg">{row.negative_share.toFixed(0)}% problem</span>
          </span>
        ) : (
          <span className="ranked-table__split-none">—</span>
        ),
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
                <button
                  key={tag}
                  type="button"
                  className="ranked-table__tag ranked-table__tag--clickable"
                  onClick={(e) => {
                    // A tag click means "show me the calls", not "narrow this
                    // dashboard" — it's a jump, not a filter toggle, so it
                    // doesn't touch the category filter this row's click sets.
                    e.stopPropagation();
                    openCalls(
                      toCallFilters(data?.filters ?? {}, {
                        tag,
                        category: undefined,
                        conversations_only: true,
                      }),
                    );
                  }}
                  title={`Open the calls tagged "${tag}"`}
                >
                  {tag}
                </button>
              ))}
            </span>
          )}
        </>
      ),
    },
    {
      key: 'review',
      header: '',
      width: '110px',
      render: (row) => (
        <OpenCallsButton
          filters={toCallFilters(data?.filters ?? {}, { category: row.key, conversations_only: true })}
        />
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
            // No longer "100%" in the last column: percentages are now share
            // of usable calls (see RankedIssuesCard docs), and one call can
            // raise several issues, so the column doesn't sum to 100 — showing
            // it as if it did would be the exact distortion this was fixed to
            // remove elsewhere on the dashboard.
            { content: totalLabel, colSpan: 2, align: 'left' },
            { content: total, align: 'right' },
            { content: 'mentions', align: 'right' },
            { content: '' },
            { content: '' },
            { content: '' },
          ]}
        />
      )}
    </Card>
  );
}
