import { RunAnalysisButton } from '../dashboard/RunAnalysisButton';
import { useDashboardRefresh } from '../../state/dashboardContext';
import './DashboardHeader.css';

interface DashboardHeaderProps {
  /** Recordings with an analysis stored — not everything discovered in the bucket. */
  analyzedCalls: number;
  usableCalls: number;
}

/** Relative to now, coarse on purpose ("2m ago" not "2m 14s ago") — this is a
 *  status hint, not a stopwatch. */
function relativeTime(date: Date): string {
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000));
  if (seconds < 45) return 'just now';
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

export function DashboardHeader({ analyzedCalls, usableCalls }: DashboardHeaderProps) {
  // Only reflects a run triggered from this browser tab, not a scheduled or
  // remote run — worded below to not overclaim it's the system's global
  // "last run" (that's Admin's Schedule panel, which reads the backend's own
  // record of it).
  const { refreshedAt } = useDashboardRefresh();

  return (
    <header className="dashboard-header">
      <div className="dashboard-header__left">
        <div className="dashboard-header__badge" aria-hidden="true">
          🎯
        </div>
        <div>
          <h1 className="dashboard-header__title">Customer Trust Improvement Mission</h1>
          <p className="dashboard-header__subtitle">Service Feedback Analysis Report</p>
          <p className="dashboard-header__tagline">
            Analysis of {analyzedCalls} Customer Service Call{analyzedCalls === 1 ? '' : 's'}
            {refreshedAt && (
              <span className="dashboard-header__refreshed">
                <span className="dashboard-header__refreshed-dot" aria-hidden="true" />
                Refreshed {relativeTime(refreshedAt)}
              </span>
            )}
          </p>
        </div>
      </div>
      <div className="dashboard-header__right">
        <RunAnalysisButton />
        <div className="dashboard-header__divider" />
        <div className="dashboard-header__icon" aria-hidden="true">
          🎧
        </div>
        <div>
          <p className="dashboard-header__stat-label">Total Service Calls (Analyzed)</p>
          <p className="dashboard-header__stat-value">{analyzedCalls}</p>
          <p className="dashboard-header__stat-caption">
            {usableCalls} usable for sentiment &amp; rating
          </p>
        </div>
      </div>
    </header>
  );
}
