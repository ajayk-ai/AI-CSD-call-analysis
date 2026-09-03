import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { RankedTable, type RankedTableColumn } from '../common/RankedTable';
import { sentimentMeta } from '../../data/presentation';
import { useAgentFilter } from '../../state/dashboardContext';
import type { AgentStats, DashboardSummary } from '../../services/api';
import './AgentPerformanceTable.css';

interface AgentPerformanceTableProps {
  data: DashboardSummary | null;
  error?: string;
}

const UNASSIGNED = 'Unassigned';

/** Per-agent rollup — sentiment mix, AI vs. stated rating, compliance issues,
 *  connection-issue rate. Ranked worst-average-rating-first by the backend,
 *  so attention goes where it's needed without extra client sorting.
 *
 *  Always shows the FULL roster regardless of the dashboard's global agent
 *  filter (see routes_dashboard.py's `by_agent` docs) — that's what makes it
 *  usable as the picker: click a name here to set that filter and every
 *  other card on the dashboard recontextualizes around them. "Unassigned"
 *  isn't a real agent_name to filter by (it's a display label for calls with
 *  no extracted name), so that row isn't clickable. */
export function AgentPerformanceTable({ data, error }: AgentPerformanceTableProps) {
  const rows = data?.by_agent ?? [];
  const { agent: selectedAgent, setAgent } = useAgentFilter();

  const columns: RankedTableColumn<AgentStats>[] = [
    {
      key: 'agent',
      header: 'Agent',
      render: (row) =>
        row.agent_name === UNASSIGNED ? (
          <span className="agent-performance__name agent-performance__name--muted">{row.agent_name}</span>
        ) : (
          <button
            type="button"
            className={`agent-performance__name-btn ${
              selectedAgent === row.agent_name ? 'agent-performance__name-btn--active' : ''
            }`}
            onClick={() => setAgent(selectedAgent === row.agent_name ? null : row.agent_name)}
            title={
              selectedAgent === row.agent_name
                ? `Clear the dashboard's agent filter`
                : `Scope the whole dashboard to ${row.agent_name}`
            }
          >
            {row.agent_name}
          </button>
        ),
    },
    { key: 'calls', header: 'Calls Handled', align: 'right', width: '110px', render: (row) => row.calls_handled },
    {
      key: 'ai_rating',
      header: 'Avg Rating (AI)',
      align: 'right',
      width: '120px',
      render: (row) => (row.average_rating !== null ? `${row.average_rating.toFixed(2)} / 10` : '—'),
    },
    {
      key: 'stated_rating',
      header: 'Avg Stated Rating',
      align: 'right',
      width: '130px',
      render: (row) => (row.average_stated_rating !== null ? `${row.average_stated_rating.toFixed(2)} / 10` : '—'),
    },
    {
      key: 'sentiment',
      header: 'Sentiment Mix',
      render: (row) => (
        <span className="agent-performance__sentiment">
          {row.sentiment.map((slice) => (
            <span key={slice.key} title={`${slice.label}: ${slice.percentage.toFixed(0)}%`}>
              {sentimentMeta(slice.key).emoji} {slice.percentage.toFixed(0)}%
            </span>
          ))}
        </span>
      ),
    },
    {
      key: 'compliance',
      header: 'Compliance Issues',
      align: 'right',
      width: '130px',
      render: (row) => row.compliance_issue_count,
    },
    {
      key: 'connection',
      header: 'Connection Issue Rate',
      align: 'right',
      width: '150px',
      render: (row) => `${row.connection_issue_rate.toFixed(1)}%`,
    },
  ];

  return (
    <Card
      title="Agent Performance"
      subtitle={data ? `Based on ${data.usable_calls} Usable Calls — click a name to drill in` : undefined}
      icon="🧑‍💼"
    >
      {error ? (
        <CardState kind="error" message={error} />
      ) : !data ? (
        <CardState kind="loading" />
      ) : rows.length === 0 ? (
        <CardState
          kind="empty"
          message="No agent-level data yet"
          hint="Agent names are extracted from the call opening — re-analyze calls to backfill this."
        />
      ) : (
        <RankedTable columns={columns} rows={rows} getRowKey={(row) => row.agent_name} />
      )}
    </Card>
  );
}
