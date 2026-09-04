import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { iconForCategory } from '../../data/presentation';
import { useDashboardFilters, useDataMode, useDashboardRefresh } from '../../state/dashboardContext';
import { toCallFilters } from '../../state/filterMapping';
import { fetchDashboardInsights, type DashboardFilters, type InsightPair } from '../../services/api';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './KeyInsights.css';

const MENTION_TYPE_LABEL: Record<string, string> = {
  negative_driver: 'complaint',
  service_issue: 'service issue',
};

function InsightTile({ insight, filters }: { insight: InsightPair; filters: DashboardFilters }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="key-insights__tile">
      <button type="button" className="key-insights__summary" onClick={() => setExpanded((e) => !e)}>
        <span className="key-insights__icon">{iconForCategory(insight.positive_category, '⭐')}</span>
        <span className="key-insights__text">
          <strong>{insight.positive_category}</strong> praised alongside{' '}
          <span className="key-insights__icon">{iconForCategory(insight.other_category, '⚠️')}</span>{' '}
          <strong>{insight.other_category}</strong> ({MENTION_TYPE_LABEL[insight.other_mention_type] ?? 'issue'}) in{' '}
          {insight.count} call{insight.count === 1 ? '' : 's'} ({insight.percentage.toFixed(1)}%)
        </span>
        <span className="key-insights__chevron">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && (
        <div className="key-insights__quotes">
          {insight.positive_example && (
            <p>
              <span className="key-insights__quote-label">Positive:</span> "{insight.positive_example}"
            </p>
          )}
          {insight.other_example && (
            <p>
              <span className="key-insights__quote-label">Issue:</span> "{insight.other_example}"
            </p>
          )}
          <div className="key-insights__review">
            {/* Both categories are mentions on the SAME calls, but /api/calls
                only takes one category to match on — this opens the issue
                side, since that's the half worth reading in full. */}
            <OpenCallsButton
              filters={toCallFilters(filters, { category: insight.other_category, conversations_only: true })}
              label={`Review the ${insight.count} calls`}
            />
          </div>
        </div>
      )}
    </li>
  );
}

/** Cross-signal correlation: positive themes that co-occur, on the same
 *  calls, with a negative driver or service issue — e.g. "service praised
 *  alongside spare-part pricing complaints in 23 calls". Not part of the
 *  shared dashboard summary cache since it's its own endpoint/shape; follows
 *  the same per-card range-selector + global-plant-filter pattern as the
 *  other cards regardless. */
export function KeyInsights() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const { filters } = useDashboardFilters();
  const { agent } = filters;
  const { dataMode } = useDataMode();
  const { refreshedAt } = useDashboardRefresh();
  const [state, setState] = useState<
    { status: 'loading' } | { status: 'ready'; insights: InsightPair[] } | { status: 'error'; message: string }
  >({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    setState({ status: 'loading' });
    fetchDashboardInsights(range, filters, dataMode)
      .then((result) => {
        if (!cancelled) setState({ status: 'ready', insights: result.insights });
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' });
      });
    return () => {
      cancelled = true;
    };
    // Serialized rather than listed field by field, so a new filter dimension
    // can't silently fail to re-trigger this card's own fetch.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, JSON.stringify(filters), dataMode, refreshedAt]);

  return (
    <Card
      title="Key Insights"
      subtitle={
        agent
          ? `${agent} — what's driving satisfaction alongside what's holding it back`
          : "What's driving satisfaction alongside what's holding it back"
      }
      icon="💡"
    >
      <TimeRangeFilter value={range} onChange={setRange} />
      {state.status === 'error' ? (
        <CardState kind="error" message={state.message} />
      ) : state.status === 'loading' ? (
        <CardState kind="loading" />
      ) : state.insights.length === 0 ? (
        <CardState
          kind="empty"
          message="No correlated insights yet"
          hint="Shows up once the same calls carry both a praised theme and a flagged issue."
        />
      ) : (
        <ul className="key-insights__list">
          {state.insights.map((insight, i) => (
            <InsightTile
              key={`${insight.positive_category}-${insight.other_category}-${i}`}
              insight={insight}
              filters={filters}
            />
          ))}
        </ul>
      )}
    </Card>
  );
}
