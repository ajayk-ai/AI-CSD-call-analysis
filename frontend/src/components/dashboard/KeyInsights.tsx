import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { TimeRangeFilter } from '../common/TimeRangeFilter';
import { iconForCategory } from '../../data/presentation';
import { useDashboardFilters, useDataMode, useDashboardRefresh } from '../../state/dashboardContext';
import { toCallFilters } from '../../state/filterMapping';
import {
  fetchAiInsights,
  fetchDashboardInsights,
  type AiInsight,
  type DashboardFilters,
  type InsightPair,
} from '../../services/api';
import type { TimeRangeKey } from '../../types/dashboard.types';
import './KeyInsights.css';

function InsightTile({ insight, filters }: { insight: InsightPair; filters: DashboardFilters }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="key-insights__tile">
      <button type="button" className="key-insights__summary" onClick={() => setExpanded((e) => !e)}>
        <span className="key-insights__icon">{iconForCategory(insight.positive_category, '⭐')}</span>
        <span className="key-insights__text">
          Customers praised <strong>{insight.positive_category}</strong> but also raised{' '}
          <strong>{insight.other_category}</strong> — {insight.count} call{insight.count === 1 ? '' : 's'} (
          {insight.percentage.toFixed(1)}%)
        </span>
        <span className="key-insights__chevron">{expanded ? '▾' : '▸'}</span>
      </button>
      {expanded && (
        <div className="key-insights__quotes">
          {insight.positive_example && (
            <p>
              <span className="key-insights__quote-label">Praise:</span> "{insight.positive_example}"
            </p>
          )}
          {insight.other_example && (
            <p>
              <span className="key-insights__quote-label">Concern:</span> "{insight.other_example}"
            </p>
          )}
          <div className="key-insights__review">
            {/* /api/calls matches one category, so this opens the concern side. */}
            <OpenCallsButton
              filters={toCallFilters(filters, { category: insight.other_category, conversations_only: true })}
              label={`Review ${insight.count} call${insight.count === 1 ? '' : 's'}`}
            />
          </div>
        </div>
      )}
    </li>
  );
}

type PairsState =
  | { status: 'loading' }
  | { status: 'ready'; insights: InsightPair[]; usableCalls: number }
  | { status: 'error'; message: string };

type HighlightsState = { status: 'idle' | 'loading' | 'error' } | { status: 'ready'; data: AiInsight };

export function KeyInsights() {
  const [range, setRange] = useState<TimeRangeKey>('all');
  const { filters } = useDashboardFilters();
  const { agent } = filters;
  const { dataMode } = useDataMode();
  const { refreshedAt } = useDashboardRefresh();
  const [pairs, setPairs] = useState<PairsState>({ status: 'loading' });
  const [highlights, setHighlights] = useState<HighlightsState>({ status: 'idle' });
  const [retry, setRetry] = useState(0);
  const filtersKey = JSON.stringify(filters);

  useEffect(() => {
    let cancelled = false;
    setPairs({ status: 'loading' });
    fetchDashboardInsights(range, filters, dataMode)
      .then((result) => {
        if (!cancelled) setPairs({ status: 'ready', insights: result.insights, usableCalls: result.usable_calls });
      })
      .catch((err: unknown) => {
        if (!cancelled) setPairs({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, filtersKey, dataMode, refreshedAt]);

  const usableCalls = pairs.status === 'ready' ? pairs.usableCalls : null;

  // Waits for the pairs request so a selection with no usable calls never
  // asks for highlights at all.
  useEffect(() => {
    if (!usableCalls) {
      setHighlights({ status: 'idle' });
      return;
    }
    let cancelled = false;
    setHighlights({ status: 'loading' });
    fetchAiInsights(range, filters, dataMode)
      .then((data) => {
        if (!cancelled) setHighlights({ status: 'ready', data });
      })
      .catch(() => {
        if (!cancelled) setHighlights({ status: 'error' });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [usableCalls, range, filtersKey, dataMode, refreshedAt, retry]);

  return (
    <Card
      title="Key Insights"
      subtitle={agent ? `${agent} — what stands out in the calls` : 'What stands out in the calls'}
      icon="💡"
    >
      <TimeRangeFilter value={range} onChange={setRange} />

      {pairs.status === 'error' ? (
        <CardState kind="error" message={pairs.message} />
      ) : pairs.status === 'loading' ? (
        <CardState kind="loading" />
      ) : pairs.usableCalls === 0 ? (
        <CardState
          kind="empty"
          message="No customer conversations in this selection yet"
          hint="Insights appear once analyzed calls include a real conversation."
        />
      ) : (
        <>
          <section className="key-insights__highlights">
            <h4 className="key-insights__heading">✨ Highlights</h4>
            {highlights.status === 'ready' ? (
              <>
                <p className="key-insights__headline">{highlights.data.headline}</p>
                <ul className="key-insights__points">
                  {highlights.data.key_points.map((point, i) => (
                    <li key={i}>{point}</li>
                  ))}
                </ul>
                <p className="key-insights__recommendation">
                  <strong>Recommended focus:</strong> {highlights.data.recommendation}
                </p>
              </>
            ) : highlights.status === 'error' ? (
              <p className="key-insights__muted">
                Highlights aren't available right now.{' '}
                <button type="button" className="key-insights__retry" onClick={() => setRetry((n) => n + 1)}>
                  Try again
                </button>
              </p>
            ) : (
              <p className="key-insights__muted">Reading the latest calls…</p>
            )}
          </section>

          {pairs.insights.length > 0 && (
            <section className="key-insights__pairs">
              <h4 className="key-insights__heading">Praise and concerns on the same calls</h4>
              <ul className="key-insights__list">
                {pairs.insights.map((insight, i) => (
                  <InsightTile
                    key={`${insight.positive_category}-${insight.other_category}-${i}`}
                    insight={insight}
                    filters={filters}
                  />
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </Card>
  );
}
