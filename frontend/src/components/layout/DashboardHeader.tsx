import { RunAnalysisButton } from '../dashboard/RunAnalysisButton';
import './DashboardHeader.css';

interface DashboardHeaderProps {
  totalCalls: number;
}

export function DashboardHeader({ totalCalls }: DashboardHeaderProps) {
  return (
    <header className="dashboard-header">
      <div className="dashboard-header__left">
        <div className="dashboard-header__badge" aria-hidden="true">
          🎯
        </div>
        <div>
          <h1 className="dashboard-header__title">Customer Trust Improvement Mission</h1>
          <p className="dashboard-header__subtitle">Service Feedback Analysis Report</p>
          <p className="dashboard-header__tagline">Analysis of First {totalCalls} Customer Service Calls</p>
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
          <p className="dashboard-header__stat-value">{totalCalls}</p>
          <p className="dashboard-header__stat-caption">First {totalCalls} Customer Service Calls</p>
        </div>
      </div>
    </header>
  );
}
