import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { iconForCategory } from '../../data/presentation';
import { toCallFilters } from '../../state/filterMapping';
import type { ApiSlice, DashboardFilters, DashboardSummary } from '../../services/api';
import './ExecutiveSummary.css';

interface ExecutiveSummaryProps {
  data: DashboardSummary | null;
  error?: string;
  filters: DashboardFilters;
}

function ratingRead(rating: number | null): string {
  if (rating === null) return 'No usable calls yet';
  if (rating >= 8.5) return 'a strong result';
  if (rating >= 7) return 'a solid result, with room to improve';
  if (rating >= 5.5) return 'below where it should be';
  return 'a serious concern';
}

/**
 * "Why are we performing this way, and what should I do about it?" — a
 * templated read of the SAME aggregate fields the rest of the dashboard
 * already fetched (top_negative_drivers, top_service_issues, sentiment,
 * average_rating). Deliberately not an LLM call: every sentence here traces
 * to a specific number already on the page, so it costs nothing per view and
 * can't say anything the data doesn't back up. A model-generated summary
 * would need its own endpoint (and its own per-view Gemini cost) — worth
 * doing later if templated wording turns out to be too rigid, but not a
 * silent substitute for it.
 */
export function ExecutiveSummary({ data, error, filters }: ExecutiveSummaryProps) {
  if (error) {
    return (
      <Card title="AI Executive Summary" icon="✨" variant="blue">
        <CardState kind="error" message={error} />
      </Card>
    );
  }
  if (!data) {
    return (
      <Card title="AI Executive Summary" icon="✨" variant="blue">
        <CardState kind="loading" />
      </Card>
    );
  }
  if (data.usable_calls === 0) {
    return (
      <Card title="AI Executive Summary" icon="✨" variant="blue">
        <CardState
          kind="empty"
          message="Not enough usable calls yet"
          hint="This fills in once analyzed calls include real conversations, not just busy tones or voicemails."
        />
      </Card>
    );
  }

  const topNegative: ApiSlice | undefined = data.top_negative_drivers[0];
  const topService: ApiSlice | undefined = data.top_service_issues[0];
  const negativeSentiment = data.sentiment.find((s) => s.key === 'negative');

  return (
    <Card title="AI Executive Summary" icon="✨" variant="blue" bodyClassName="exec-summary">
      <p className="exec-summary__lead">
        Overall satisfaction is <strong>{data.average_rating?.toFixed(2) ?? '—'} / 10</strong> —{' '}
        {ratingRead(data.average_rating)}
        {negativeSentiment && negativeSentiment.count > 0 && (
          <>
            {' '}
            ({negativeSentiment.percentage.toFixed(0)}% of usable calls read negative overall).
          </>
        )}
      </p>

      <div className="exec-summary__grid">
        <div className="exec-summary__point">
          <span className="exec-summary__icon">
            {topNegative ? iconForCategory(topNegative.key, '⚠️') : '✅'}
          </span>
          <div>
            <div className="exec-summary__point-label">Top concern</div>
            {topNegative ? (
              <>
                <div className="exec-summary__point-value">{topNegative.label}</div>
                <div className="exec-summary__point-detail">
                  {topNegative.count} call{topNegative.count === 1 ? '' : 's'} (
                  {topNegative.percentage.toFixed(1)}% of usable calls)
                </div>
                <OpenCallsButton
                  filters={toCallFilters(filters, { category: topNegative.key, conversations_only: true })}
                  label="Review calls"
                />
              </>
            ) : (
              <div className="exec-summary__point-value">No significant negative drivers</div>
            )}
          </div>
        </div>

        <div className="exec-summary__point">
          <span className="exec-summary__icon">{topService ? iconForCategory(topService.key) : '🔧'}</span>
          <div>
            <div className="exec-summary__point-label">Most reported machine issue</div>
            {topService ? (
              <>
                <div className="exec-summary__point-value">{topService.label}</div>
                <div className="exec-summary__point-detail">
                  {topService.count} call{topService.count === 1 ? '' : 's'} (
                  {topService.percentage.toFixed(1)}% of usable calls)
                </div>
                <OpenCallsButton
                  filters={toCallFilters(filters, { category: topService.key, conversations_only: true })}
                  label="Review calls"
                />
              </>
            ) : (
              <div className="exec-summary__point-value">No service issues reported</div>
            )}
          </div>
        </div>
      </div>

      <p className="exec-summary__recommendation">
        <strong>Recommended focus:</strong>{' '}
        {topNegative
          ? `address "${topNegative.label}" — it's the single largest driver of negative feedback right now.`
          : 'no single driver stands out yet — keep monitoring as more calls come in.'}
      </p>
    </Card>
  );
}
