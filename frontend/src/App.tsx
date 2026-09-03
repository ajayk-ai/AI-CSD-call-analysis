import { useState } from 'react';
import './App.css';
import { PlantFilter } from './components/common/PlantFilter';
import { AgentFilter } from './components/common/AgentFilter';
import { DataModeBanner } from './components/common/DataModeBanner';
import { FilterChips } from './components/common/FilterChips';
import { DashboardHeader } from './components/layout/DashboardHeader';
import { TabNav, type TabKey } from './components/layout/TabNav';
import { CallQualitySummary } from './components/dashboard/CallQualitySummary';
import { CallConnectionSummary } from './components/dashboard/CallConnectionSummary';
import { SentimentOverview } from './components/dashboard/SentimentOverview';
import { SatisfactionRating } from './components/dashboard/SatisfactionRating';
import { TrendComparison } from './components/dashboard/TrendComparison';
import { IssueAnalysisTable } from './components/dashboard/IssueAnalysisTable';
import { ServiceIssuesTable } from './components/dashboard/ServiceIssuesTable';
import { AgentComplianceSummary } from './components/dashboard/AgentComplianceSummary';
import { ComplianceIssuesTable } from './components/dashboard/ComplianceIssuesTable';
import { AgentPerformanceTable } from './components/dashboard/AgentPerformanceTable';
import { KeyInsights } from './components/dashboard/KeyInsights';
import { AdminPage } from './pages/AdminPage';
import { CallsPage } from './pages/CallsPage';
import { displayData, usePlantFilter, useAgentFilter, useDashboardSummary } from './state/dashboardContext';
import { DashboardDataProvider } from './state/dashboardData';

/**
 * The donut cards carry their own time filter and fetch their own range.
 * Everything else reads the "all" summary, which is what this component holds.
 *
 * All the other filters are global — one selection for the whole page — and
 * every `useDashboardSummary` call picks them up automatically via context, so
 * nothing has to be passed down. Plant and Agent have explicit dropdowns; the
 * rest are set by clicking a slice or row on a KPI card, and every active one
 * shows up in <FilterChips> so it can always be undone.
 */
function Dashboard() {
  const state = useDashboardSummary('all');
  const data = displayData(state);
  const error = state.status === 'error' ? state.message : undefined;
  const { plant, setPlant, plants } = usePlantFilter();
  const { agent, setAgent, agents } = useAgentFilter();

  return (
    <div className="dashboard">
      <DashboardHeader
        analyzedCalls={data?.analyzed_calls ?? 0}
        usableCalls={data?.usable_calls ?? 0}
      />

      <div className="dashboard__filters">
        <PlantFilter plants={plants} value={plant} onChange={setPlant} />
        <AgentFilter agents={agents} value={agent} onChange={setAgent} />
      </div>
      <FilterChips />
      <DataModeBanner />

      {error && (
        <div className="dashboard__banner" role="alert">
          <strong>Can't load the dashboard.</strong> {error}
        </div>
      )}

      <div className="dashboard__row dashboard__row--four">
        <CallQualitySummary />
        <SentimentOverview />
        <SatisfactionRating />
        <TrendComparison data={data} error={error} />
      </div>

      <div className="dashboard__row dashboard__row--two">
        <CallConnectionSummary />
        <AgentComplianceSummary />
      </div>

      <div className="dashboard__row dashboard__row--two">
        <IssueAnalysisTable data={data} error={error} />
        <ServiceIssuesTable data={data} error={error} />
      </div>

      <div className="dashboard__row dashboard__row--two">
        <ComplianceIssuesTable data={data} error={error} />
        <KeyInsights />
      </div>

      <div className="dashboard__row dashboard__row--one">
        <AgentPerformanceTable data={data} error={error} />
      </div>
    </div>
  );
}

function App() {
  const [tab, setTab] = useState<TabKey>('dashboard');

  return (
    <DashboardDataProvider>
      <TabNav active={tab} onChange={setTab} />
      {tab === 'dashboard' && <Dashboard />}
      {tab === 'calls' && <CallsPage />}
      {tab === 'admin' && <AdminPage />}
    </DashboardDataProvider>
  );
}

export default App;
