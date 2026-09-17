import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { OpenCallsButton } from '../common/OpenCallsButton';
import { iconForCategory } from '../../data/presentation';
import { toCallFilters } from '../../state/filterMapping';
import type { CallFilters, DashboardFilters, DashboardSummary } from '../../services/api';
import './ExecutiveSummary.css';

interface ExecutiveSummaryProps {
  data: DashboardSummary | null;
  error?: string;
  filters: DashboardFilters;
}

interface Point {
  key: string;
  icon: string;
  label: string;
  value: string;
  detail: string;
  tone: 'bad' | 'good' | 'neutral';
  review?: CallFilters;
}

interface Action {
  /** Higher = more urgent. Only used to rank actions against each other. */
  severity: number;
  text: string;
}

const MIN_CALLS_FOR_TREND = 8;
const MIN_AGENT_CALLS = 5;
const DROPPED = ['dropped_during_call', 'dropped_at_greeting'];
const NOT_PICKED_UP = ['no_answer_busy', 'voicemail_ivr_only'];

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`;

function ratingRead(rating: number | null): string {
  if (rating === null) return 'not rated yet';
  if (rating >= 8.5) return 'a strong result';
  if (rating >= 7) return 'a solid result, with room to improve';
  if (rating >= 5.5) return 'below where it should be';
  return 'a serious concern';
}

/** Month-to-date rating (weighted by calls per day) against last month's
 *  average — the same comparison as the Average Rating tile. */
function ratingTrend(data: DashboardSummary): { current: number; previous: number; month: string } | null {
  const previous = data.monthly_averages.at(-1);
  let sum = 0;
  let calls = 0;
  for (const day of data.daily_ratings) {
    sum += day.rating * day.call_count;
    calls += day.call_count;
  }
  if (!previous || calls < MIN_CALLS_FOR_TREND) return null;
  return { current: sum / calls, previous: previous.avg_rating, month: data.current_month_label ?? 'This month' };
}

/**
 * A rule-based read of the numbers already on the dashboard: every tile and
 * sentence traces to a specific figure, so it's instant, free, and can't
 * claim anything the data doesn't show. Tiles only appear for areas that
 * have data, and the recommendation ranks what's actually worst right now
 * instead of always pointing at the top complaint.
 */
function buildSummary(data: DashboardSummary, filters: DashboardFilters) {
  const points: Point[] = [];
  const actions: Action[] = [];
  const review = (extra: CallFilters) => toCallFilters(filters, { ...extra, conversations_only: true });

  const concern = data.top_negative_drivers[0];
  if (concern) {
    points.push({
      key: 'concern',
      icon: iconForCategory(concern.key, '⚠️'),
      label: 'Top concern',
      value: concern.label,
      detail: `${plural(concern.count, 'call')} · ${concern.percentage.toFixed(1)}% of conversations`,
      tone: 'bad',
      review: review({ category: concern.key }),
    });
    actions.push({
      severity: concern.percentage,
      text: `Fix "${concern.label}" — it comes up in ${concern.percentage.toFixed(0)}% of conversations, more than any other complaint.`,
    });
  }

  const machine = data.top_service_issues[0];
  if (machine) {
    points.push({
      key: 'machine',
      icon: iconForCategory(machine.key, '🔧'),
      label: 'Most reported machine issue',
      value: machine.label,
      detail: `${plural(machine.count, 'call')} · ${machine.percentage.toFixed(1)}% of conversations`,
      tone: 'bad',
      review: review({ category: machine.key }),
    });
    actions.push({
      severity: machine.percentage * 0.8,
      text: `Look into "${machine.label}" with the service team — it's the most reported machine issue (${plural(machine.count, 'call')}).`,
    });
  }

  const praise = data.top_positive_themes[0];
  if (praise) {
    points.push({
      key: 'praise',
      icon: iconForCategory(praise.key, '⭐'),
      label: 'What customers value most',
      value: praise.label,
      detail: `Praised in ${plural(praise.count, 'call')} · ${praise.percentage.toFixed(1)}%`,
      tone: 'good',
      review: review({ category: praise.key }),
    });
  }

  const followed = data.script_adherence.find((s) => s.key === 'followed');
  const complianceIssue = data.top_compliance_issues[0];
  if (followed || complianceIssue) {
    const followedPct = followed?.percentage ?? 0;
    points.push({
      key: 'compliance',
      icon: '📋',
      label: 'Script compliance',
      value: `${followedPct.toFixed(0)}% of calls follow the script`,
      detail: complianceIssue
        ? `Most common slip: ${complianceIssue.label} (${plural(complianceIssue.count, 'call')})`
        : 'No recurring slips found',
      tone: followedPct >= 75 ? 'good' : 'bad',
      review: complianceIssue ? review({ category: complianceIssue.key }) : undefined,
    });
    if (followedPct < 75) {
      actions.push({
        severity: (100 - followedPct) * 0.3,
        text: complianceIssue
          ? `Coach agents on "${complianceIssue.label}" — only ${followedPct.toFixed(0)}% of calls follow the script.`
          : `Coach agents on the call script — only ${followedPct.toFixed(0)}% of calls follow it.`,
      });
    }
  }

  const trend = ratingTrend(data);
  if (trend) {
    const delta = trend.current - trend.previous;
    const flat = Math.abs(delta) < 0.05;
    points.push({
      key: 'trend',
      icon: flat ? '➖' : delta > 0 ? '📈' : '📉',
      label: 'Rating trend',
      value: flat ? 'Steady vs last month' : `${delta > 0 ? 'Up' : 'Down'} ${Math.abs(delta).toFixed(1)} vs last month`,
      detail: `${trend.month} so far ${trend.current.toFixed(2)} · last month ${trend.previous.toFixed(2)}`,
      tone: flat ? 'neutral' : delta > 0 ? 'good' : 'bad',
    });
    if (delta <= -0.5) {
      actions.push({
        severity: Math.abs(delta) * 20,
        text: `Find out what changed this month — the rating is down ${Math.abs(delta).toFixed(1)} points from last month.`,
      });
    }
  }

  // Only real drops: "no answer / busy" and voicemail are the customer not
  // picking up, which usually dwarfs everything else and isn't a line problem.
  const drops = data.connection_status.filter((s) => DROPPED.includes(s.key));
  const dropCount = drops.reduce((n, s) => n + s.count, 0);
  const pickedUp = data.connection_status
    .filter((s) => !NOT_PICKED_UP.includes(s.key))
    .reduce((n, s) => n + s.count, 0);
  const dropPct = pickedUp > 0 ? (dropCount / pickedUp) * 100 : 0;
  const worstDrop = [...drops].sort((a, b) => b.count - a.count)[0];
  if (dropCount > 0 && worstDrop) {
    points.push({
      key: 'connection',
      icon: '📶',
      label: 'Dropped calls',
      value: `${dropPct.toFixed(0)}% of picked-up calls dropped`,
      detail: `${plural(dropCount, 'call')} · mostly ${worstDrop.key === 'dropped_at_greeting' ? 'at the greeting' : 'mid-call'}`,
      tone: dropPct >= 10 ? 'bad' : 'neutral',
      review: toCallFilters(filters, { connection_status: worstDrop.key }),
    });
    if (dropPct >= 10) {
      actions.push({
        severity: dropPct * 0.5,
        text: `Check line quality — ${dropPct.toFixed(0)}% of picked-up calls dropped.`,
      });
    }
  }

  const rated = data.by_agent.filter(
    (a) => a.average_rating !== null && a.agent_name !== 'Unassigned' && a.calls_handled >= MIN_AGENT_CALLS,
  );
  if (rated.length >= 2 && data.average_rating !== null) {
    const weakest = rated.reduce((a, b) => ((a.average_rating ?? 0) <= (b.average_rating ?? 0) ? a : b));
    const gap = data.average_rating - (weakest.average_rating ?? 0);
    if (gap >= 0.5) {
      points.push({
        key: 'agent',
        icon: '👤',
        label: 'Agent needing support',
        value: weakest.agent_name,
        detail: `${weakest.average_rating?.toFixed(2)} / 10 over ${plural(weakest.calls_handled, 'call')} · ${gap.toFixed(1)} below average`,
        tone: 'bad',
        review: toCallFilters(filters, { agent_name: weakest.agent_name, conversations_only: true }),
      });
      actions.push({
        severity: gap * 6,
        text: `Support ${weakest.agent_name} — rated ${gap.toFixed(1)} points below the team average.`,
      });
    }
  }

  actions.sort((a, b) => b.severity - a.severity);
  return { points, actions: actions.slice(0, 2) };
}

export function ExecutiveSummary({ data, error, filters }: ExecutiveSummaryProps) {
  const title = 'Executive Summary';
  const icon = '🧭';

  if (error) {
    return (
      <Card title={title} icon={icon} variant="blue">
        <CardState kind="error" message={error} />
      </Card>
    );
  }
  if (!data) {
    return (
      <Card title={title} icon={icon} variant="blue">
        <CardState kind="loading" />
      </Card>
    );
  }
  if (data.usable_calls === 0) {
    return (
      <Card title={title} icon={icon} variant="blue">
        <CardState
          kind="empty"
          message="No customer conversations yet"
          hint="The summary appears once analyzed calls include a real conversation."
        />
      </Card>
    );
  }

  const { points, actions } = buildSummary(data, filters);
  const positive = data.sentiment.find((s) => s.key === 'positive');
  const negative = data.sentiment.find((s) => s.key === 'negative');

  return (
    <Card title={title} icon={icon} variant="blue" bodyClassName="exec-summary">
      <p className="exec-summary__lead">
        Across <strong>{data.usable_calls.toLocaleString()} conversations</strong>, customers rate us{' '}
        <strong>{data.average_rating?.toFixed(2) ?? '—'} / 10</strong> — {ratingRead(data.average_rating)}.
        {(positive || negative) && (
          <>
            {' '}
            {(positive?.percentage ?? 0).toFixed(0)}% of calls were positive and{' '}
            {(negative?.percentage ?? 0).toFixed(0)}% negative.
          </>
        )}
      </p>

      <div className="exec-summary__grid">
        {points.map((point) => (
          <div key={point.key} className={`exec-summary__point exec-summary__point--${point.tone}`}>
            <span className="exec-summary__icon">{point.icon}</span>
            <div>
              <div className="exec-summary__point-label">{point.label}</div>
              <div className="exec-summary__point-value">{point.value}</div>
              <div className="exec-summary__point-detail">{point.detail}</div>
              {point.review && <OpenCallsButton filters={point.review} label="Review calls" />}
            </div>
          </div>
        ))}
      </div>

      <div className="exec-summary__recommendation">
        <strong>Recommended focus</strong>
        {actions.length === 0 ? (
          <p>Nothing stands out as urgent — keep monitoring as new calls come in.</p>
        ) : (
          <ol>
            {actions.map((action) => (
              <li key={action.text}>{action.text}</li>
            ))}
          </ol>
        )}
      </div>
    </Card>
  );
}
