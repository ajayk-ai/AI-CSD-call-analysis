import { Fragment, useEffect, useMemo, useState } from 'react';
import { Card } from '../components/common/Card';
import { CardState } from '../components/common/CardState';
import { PlantFilter } from '../components/common/PlantFilter';
import { DataModeBanner } from '../components/common/DataModeBanner';
import { usePlantFilter, useDataMode } from '../state/dashboardContext';
import { useNavigation } from '../state/navigation';
import { iconForCategory, qualityColor, sentimentMeta } from '../data/presentation';
import {
  callAudioUrl,
  fetchCallDetail,
  fetchCalls,
  fetchDashboardAgents,
  type CallDetail,
  type CallFilters,
  type CallListItem,
  type CallSortKey,
} from '../services/api';
import './CallsPage.css';

const PAGE_SIZE = 25;

const STATUS_META: Record<string, { label: string; color: string }> = {
  analyzed: { label: 'Analyzed', color: 'var(--color-good)' },
  failed: { label: 'Failed', color: 'var(--color-bad)' },
  analyzing: { label: 'Analyzing', color: 'var(--color-warning)' },
  pending: { label: 'Pending', color: 'var(--text-muted)' },
};

const MENTION_GROUPS: { type: string; label: string }[] = [
  { type: 'negative_driver', label: 'Negative Drivers' },
  { type: 'service_issue', label: 'Service / Machine Issues' },
  { type: 'positive_theme', label: 'Positive Themes' },
  { type: 'agent_compliance', label: 'Agent Compliance Issues' },
];

const STATUS_OPTIONS = ['pending', 'analyzing', 'analyzed', 'failed'];
const QUALITY_OPTIONS = ['good_clear', 'partial_usable', 'rejected_corrupted'];
const SENTIMENT_OPTIONS = ['positive', 'neutral', 'negative'];

interface SortableColumn {
  key: CallSortKey | null;
  label: string;
  className: string;
  align?: 'right';
}

const COLUMNS: SortableColumn[] = [
  { key: null, label: 'ID', className: 'col--id' },
  { key: 'recording_date', label: 'Date', className: 'col--date' },
  { key: 'team_code', label: 'Team', className: 'col--team' },
  { key: 'agent_name', label: 'Agent', className: 'col--agent' },
  { key: 'status', label: 'Status', className: 'col--status' },
  { key: 'call_quality', label: 'Quality', className: 'col--quality' },
  { key: 'sentiment', label: 'Sentiment', className: 'col--sentiment' },
  { key: 'satisfaction_rating', label: 'Rating', className: 'col--rating', align: 'right' },
];

const EMPTY_FILTERS: CallFilters = {};

function formatDate(call: CallListItem): string {
  if (call.recording_date) return call.recording_date;
  return new Date(call.created_at).toLocaleDateString();
}

function truncate(text: string | null, max = 90): string {
  if (!text) return '—';
  return text.length > max ? `${text.slice(0, max)}…` : text;
}

function titleCase(value: string): string {
  return value.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

type DetailState = { status: 'loading' } | { status: 'ready'; data: CallDetail } | { status: 'error'; message: string };

export function CallsPage() {
  const { plant, setPlant, plants } = usePlantFilter();
  const { dataMode } = useDataMode();
  const { pendingCallFilters, consumeCallFilters } = useNavigation();
  const [agents, setAgents] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const [calls, setCalls] = useState<CallListItem[]>([]);
  const [hasNext, setHasNext] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, DetailState>>({});
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const [sortBy, setSortBy] = useState<CallSortKey>('created_at');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');
  const [filters, setFilters] = useState<CallFilters>(EMPTY_FILTERS);
  // Free-text inputs (rating/date/search) are staged locally and only pushed
  // into `filters` on blur/Enter — otherwise every keystroke would refetch.
  const [ratingMinText, setRatingMinText] = useState('');
  const [ratingMaxText, setRatingMaxText] = useState('');
  const [searchText, setSearchText] = useState('');

  useEffect(() => {
    fetchDashboardAgents(dataMode)
      .then((result) => setAgents(result.agents))
      .catch(() => undefined);
  }, [dataMode]);

  // A "Review calls" click from the dashboard hands this page a ready-made
  // filter (see state/navigation.tsx). App.tsx unmounts this page whenever the
  // Calls tab isn't active, so it remounts fresh on every visit — a plain
  // mount effect is enough to pick the seed up, and `consumeCallFilters`
  // clears it so a later manual visit to this tab doesn't replay it.
  useEffect(() => {
    if (pendingCallFilters) {
      setFilters(pendingCallFilters);
      consumeCallFilters();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Plant/mode/sort/filter changes reset paging — a re-filtered set has its own page 1.
  useEffect(() => {
    setOffset(0);
  }, [plant, dataMode, sortBy, sortDir, filters]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchCalls({ limit: PAGE_SIZE + 1, offset, plant, sortBy, sortDir, filters, dataMode })
      .then((rows) => {
        if (cancelled) return;
        setHasNext(rows.length > PAGE_SIZE);
        setCalls(rows.slice(0, PAGE_SIZE));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : 'Unknown error');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [offset, plant, dataMode, sortBy, sortDir, filters]);

  const hasActiveFilters = useMemo(
    () => Object.values(filters).some((v) => v !== undefined && v !== ''),
    [filters],
  );

  const setFilter = (key: keyof CallFilters, value: string | number | undefined) => {
    setFilters((current) => {
      const next = { ...current };
      if (value === undefined || value === '') {
        delete next[key];
      } else {
        (next as Record<string, string | number>)[key] = value;
      }
      return next;
    });
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setRatingMinText('');
    setRatingMaxText('');
    setSearchText('');
  };

  const toggleSort = (key: CallSortKey) => {
    if (sortBy === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(key);
      setSortDir('asc');
    }
  };

  const toggleRow = (call: CallListItem) => {
    const nextExpanded = expandedId === call.id ? null : call.id;
    setExpandedId(nextExpanded);
    if (nextExpanded && !details[call.id]) {
      setDetails((current) => ({ ...current, [call.id]: { status: 'loading' } }));
      fetchCallDetail(call.id)
        .then((data) => setDetails((current) => ({ ...current, [call.id]: { status: 'ready', data } })))
        .catch((err: unknown) =>
          setDetails((current) => ({
            ...current,
            [call.id]: { status: 'error', message: err instanceof Error ? err.message : 'Unknown error' },
          })),
        );
    }
  };

  const copyId = (id: string) => {
    navigator.clipboard
      ?.writeText(id)
      .then(() => {
        setCopiedId(id);
        setTimeout(() => setCopiedId((current) => (current === id ? null : current)), 1500);
      })
      // Clipboard access can be denied by browser permissions/policy — the
      // button just doesn't flip to a checkmark, nothing else to do about it.
      .catch(() => undefined);
  };

  return (
    <div className="calls-page">
      <header className="calls-page__header">
        <h1 className="calls-page__title">Calls</h1>
        <p className="calls-page__subtitle">
          Every recording behind the dashboard's numbers — transcript, audio and analysis, one row per call.
        </p>
      </header>

      <PlantFilter plants={plants} value={plant} onChange={setPlant} />
      <DataModeBanner />

      {/* category/tag/connection_status have no dropdown of their own — they
          only ever arrive via a "Review calls" link from the dashboard, so
          this is the one place that makes the resulting filter legible. */}
      {(filters.category || filters.tag || filters.connection_status) && (
        <div className="calls-page__seeded-filter" role="status">
          <span>
            🔎 Showing calls
            {filters.category && (
              <>
                {' '}
                mentioning <strong>{filters.category}</strong>
              </>
            )}
            {filters.tag && (
              <>
                {' '}
                tagged <strong>{filters.tag}</strong>
              </>
            )}
            {filters.connection_status && (
              <>
                {' '}
                with connection status <strong>{titleCase(filters.connection_status)}</strong>
              </>
            )}
          </span>
          <button
            type="button"
            onClick={() => {
              setFilter('category', undefined);
              setFilter('tag', undefined);
              setFilter('connection_status', undefined);
            }}
          >
            Clear
          </button>
        </div>
      )}

      <div className="calls-filters">
        <div className="calls-filters__field">
          <label>Status</label>
          <select value={filters.status ?? ''} onChange={(e) => setFilter('status', e.target.value || undefined)}>
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {titleCase(s)}
              </option>
            ))}
          </select>
        </div>

        <div className="calls-filters__field">
          <label>Quality</label>
          <select
            value={filters.call_quality ?? ''}
            onChange={(e) => setFilter('call_quality', e.target.value || undefined)}
          >
            <option value="">All</option>
            {QUALITY_OPTIONS.map((q) => (
              <option key={q} value={q}>
                {titleCase(q)}
              </option>
            ))}
          </select>
        </div>

        <div className="calls-filters__field">
          <label>Sentiment</label>
          <select
            value={filters.sentiment ?? ''}
            onChange={(e) => setFilter('sentiment', e.target.value || undefined)}
          >
            <option value="">All</option>
            {SENTIMENT_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {titleCase(s)}
              </option>
            ))}
          </select>
        </div>

        <div className="calls-filters__field">
          <label>Agent</label>
          <select
            value={filters.agent_name ?? ''}
            onChange={(e) => setFilter('agent_name', e.target.value || undefined)}
          >
            <option value="">All</option>
            {agents.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>

        <div className="calls-filters__field calls-filters__field--range">
          <label>Rating</label>
          <div className="calls-filters__range">
            <input
              type="number"
              min={1}
              max={10}
              placeholder="Min"
              value={ratingMinText}
              onChange={(e) => setRatingMinText(e.target.value)}
              onBlur={() => setFilter('rating_min', ratingMinText ? Number(ratingMinText) : undefined)}
              onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
            />
            <span>–</span>
            <input
              type="number"
              min={1}
              max={10}
              placeholder="Max"
              value={ratingMaxText}
              onChange={(e) => setRatingMaxText(e.target.value)}
              onBlur={() => setFilter('rating_max', ratingMaxText ? Number(ratingMaxText) : undefined)}
              onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
            />
          </div>
        </div>

        <div className="calls-filters__field calls-filters__field--range">
          <label>Date</label>
          <div className="calls-filters__range">
            <input
              type="date"
              value={filters.date_from ?? ''}
              onChange={(e) => setFilter('date_from', e.target.value || undefined)}
            />
            <span>–</span>
            <input
              type="date"
              value={filters.date_to ?? ''}
              onChange={(e) => setFilter('date_to', e.target.value || undefined)}
            />
          </div>
        </div>

        <div className="calls-filters__field calls-filters__field--search">
          <label>Search</label>
          <input
            type="text"
            placeholder="Team, file, summary…"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            onBlur={() => setFilter('search', searchText || undefined)}
            onKeyDown={(e) => e.key === 'Enter' && (e.target as HTMLInputElement).blur()}
          />
        </div>

        {hasActiveFilters && (
          <button type="button" className="calls-filters__clear" onClick={clearFilters}>
            Clear filters
          </button>
        )}
      </div>

      <Card title="Call Records" icon="📞" bodyClassName="calls-table-body">
        {error ? (
          <CardState kind="error" message={error} />
        ) : loading && calls.length === 0 ? (
          <CardState kind="loading" />
        ) : calls.length === 0 ? (
          <CardState kind="empty" message="No calls found" hint="Try a different plant or filter." />
        ) : (
          <>
            <div className="calls-table-scroll">
              <table className="calls-table">
                <colgroup>
                  {COLUMNS.map((col) => (
                    <col key={col.label} className={col.className} />
                  ))}
                  <col />
                  <col className="col--chevron" />
                </colgroup>
                <thead>
                  <tr>
                    {COLUMNS.map((col) => (
                      <th
                        key={col.label}
                        className={col.key ? 'calls-table__sortable' : undefined}
                        style={col.align ? { textAlign: col.align } : undefined}
                        onClick={col.key ? () => toggleSort(col.key as CallSortKey) : undefined}
                      >
                        {col.label}
                        {col.key && sortBy === col.key && (
                          <span className="calls-table__sort-arrow">{sortDir === 'asc' ? ' ▲' : ' ▼'}</span>
                        )}
                      </th>
                    ))}
                    <th>Summary</th>
                    <th aria-label="Expand" />
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call) => {
                    const isExpanded = expandedId === call.id;
                    const status = STATUS_META[call.status] ?? { label: call.status, color: 'var(--text-muted)' };
                    const quality = call.analysis?.call_quality;
                    const sentiment = call.analysis?.sentiment;

                    return (
                      <Fragment key={call.id}>
                        <tr
                          className={`calls-table__row ${isExpanded ? 'calls-table__row--expanded' : ''}`}
                          onClick={() => toggleRow(call)}
                        >
                          <td>
                            <div className="calls-table__id">
                              {call.is_synthetic && (
                                <span className="calls-table__synthetic-badge" title="Synthetic (dummy) data">
                                  SYN
                                </span>
                              )}
                              <code title={call.id}>{call.id.slice(0, 8)}</code>
                              <button
                                type="button"
                                className="calls-table__copy"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  copyId(call.id);
                                }}
                                title="Copy full ID"
                              >
                                {copiedId === call.id ? '✓' : '⧉'}
                              </button>
                            </div>
                          </td>
                          <td>{formatDate(call)}</td>
                          <td>{call.team_code ?? '—'}</td>
                          <td>{call.analysis?.agent_name ?? '—'}</td>
                          <td>
                            <span className="calls-table__dot" style={{ background: status.color }} />
                            {status.label}
                          </td>
                          <td>
                            {quality ? (
                              <span style={{ color: qualityColor(quality) }}>{quality.replace(/_/g, ' ')}</span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td>
                            {sentiment ? (
                              <span>
                                {sentimentMeta(sentiment).emoji} {sentiment}
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td style={{ textAlign: 'right' }}>{call.analysis?.satisfaction_rating ?? '—'}</td>
                          <td className="calls-table__summary">{truncate(call.analysis?.summary ?? null)}</td>
                          <td className="calls-table__chevron">{isExpanded ? '▾' : '▸'}</td>
                        </tr>
                        {isExpanded && (
                          <tr className="calls-table__detail-row">
                            <td colSpan={COLUMNS.length + 2}>
                              <CallDetailPanel state={details[call.id]} callId={call.id} />
                            </td>
                          </tr>
                        )}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="calls-table__pager">
              <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>
                ← Prev
              </button>
              <span>{loading ? 'Loading…' : `Showing ${offset + 1}–${offset + calls.length}`}</span>
              <button type="button" disabled={!hasNext} onClick={() => setOffset(offset + PAGE_SIZE)}>
                Next →
              </button>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}

/**
 * The transcript, in English or as it was actually spoken.
 *
 * The transcription step produces both (see backend kpi_registry), because
 * they answer different questions: the English one is what a reviewer can
 * read and what every KPI node reasons over, while the verbatim one is the
 * record of what was said — the version a quote has to come from. The toggle
 * only appears when there's a genuine choice: an all-English call, or one
 * analyzed before the translation step existed, just shows its transcript.
 */
function TranscriptBlock({ transcript }: { transcript: CallDetail['transcript'] }) {
  const [showOriginal, setShowOriginal] = useState(false);

  if (!transcript) {
    return (
      <div className="call-detail__block">
        <h4>Transcript</h4>
        <p className="call-detail__empty">No transcript available for this call.</p>
      </div>
    );
  }

  const english = transcript.english_text;
  const hasBoth = Boolean(english) && english !== transcript.text;
  const body = hasBoth && !showOriginal ? (english as string) : transcript.text;

  return (
    <div className="call-detail__block">
      <h4>
        Transcript
        {hasBoth && (
          <span className="call-detail__transcript-toggle">
            {(['English', 'Original'] as const).map((option) => {
              const isOriginal = option === 'Original';
              return (
                <button
                  key={option}
                  type="button"
                  aria-pressed={showOriginal === isOriginal}
                  className={showOriginal === isOriginal ? 'is-active' : ''}
                  onClick={() => setShowOriginal(isOriginal)}
                >
                  {option}
                  {isOriginal && transcript.language_code ? ` (${transcript.language_code})` : ''}
                </button>
              );
            })}
          </span>
        )}
      </h4>
      <div className="call-detail__transcript">{body}</div>
    </div>
  );
}

function CallDetailPanel({ state, callId }: { state: DetailState | undefined; callId: string }) {
  if (!state || state.status === 'loading') {
    return <CardState kind="loading" />;
  }
  if (state.status === 'error') {
    return <CardState kind="error" message={state.message} />;
  }

  const { data } = state;
  const groupedMentions = MENTION_GROUPS.map((group) => ({
    ...group,
    mentions: data.mentions.filter((m) => m.mention_type === group.type),
  })).filter((group) => group.mentions.length > 0);

  return (
    <div className="call-detail">
      <div className="call-detail__audio">
        <audio controls preload="none" src={callAudioUrl(callId)}>
          Your browser does not support audio playback.
        </audio>
      </div>

      {data.analysis && (
        <div className="call-detail__meta">
          {data.analysis.agent_name && (
            <span className="call-detail__meta-item">
              🧑‍💼 Agent: <strong>{data.analysis.agent_name}</strong>
            </span>
          )}
          <span className="call-detail__meta-item">
            📶 Connection: <strong>{titleCase(data.analysis.connection_status)}</strong>
          </span>
          <span className="call-detail__meta-item">
            📋 Script: <strong>{titleCase(data.analysis.script_adherence)}</strong>
          </span>
          <span className="call-detail__meta-item">
            ⭐ AI Rating: <strong>{data.analysis.satisfaction_rating}/10</strong>
          </span>
          <span className="call-detail__meta-item">
            🗣️ Stated Rating:{' '}
            <strong>{data.analysis.customer_stated_rating != null ? `${data.analysis.customer_stated_rating}/10` : 'Not Given'}</strong>
          </span>
        </div>
      )}

      {data.analysis?.summary && (
        <div className="call-detail__block">
          <h4>Summary</h4>
          <p>{data.analysis.summary}</p>
        </div>
      )}

      {data.analysis?.sentiment_summary && (
        <div className="call-detail__block">
          <h4>
            Sentiment
            {data.analysis.sentiment && ` — ${sentimentMeta(data.analysis.sentiment).emoji} ${data.analysis.sentiment}`}
          </h4>
          <p>{data.analysis.sentiment_summary}</p>
        </div>
      )}

      <TranscriptBlock transcript={data.transcript} />

      {groupedMentions.length > 0 && (
        <div className="call-detail__mentions">
          {groupedMentions.map((group) => (
            <div key={group.type} className="call-detail__block">
              <h4>{group.label}</h4>
              <ul>
                {group.mentions.map((mention, i) => (
                  <li key={i}>
                    <span>{iconForCategory(mention.category)}</span> <strong>{mention.category}</strong>
                    {mention.quote && <span className="call-detail__quote"> — "{mention.quote}"</span>}
                    {mention.tags.length > 0 && (
                      <span className="call-detail__tags">
                        {mention.tags.map((tag) => (
                          <span key={tag} className="call-detail__tag">
                            {tag}
                          </span>
                        ))}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
