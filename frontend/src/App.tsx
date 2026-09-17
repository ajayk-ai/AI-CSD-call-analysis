import './App.css';
import { PlantFilter } from './components/common/PlantFilter';
import { AgentFilter } from './components/common/AgentFilter';
import { DataModeBanner } from './components/common/DataModeBanner';
import { FilterChips } from './components/common/FilterChips';
import { DashboardHeader } from './components/layout/DashboardHeader';
import { TabNav } from './components/layout/TabNav';
import { SectionNav } from './components/layout/SectionNav';
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
import { KpiSummaryStrip } from './components/dashboard/KpiSummaryStrip';
import { ExecutiveSummary } from './components/dashboard/ExecutiveSummary';
import { AdminPage } from './pages/AdminPage';
import { CallsPage } from './pages/CallsPage';
import {
  displayData,
  usePlantFilter,
  useAgentFilter,
  useDashboardFilters,
  useDashboardSummary,
} from './state/dashboardContext';
import { DashboardDataProvider } from './state/dashboardData';
import { NavigationProvider, useNavigation } from './state/navigation';

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
  const { filters } = useDashboardFilters();
  const { section, setSection } = useNavigation();

  return (
    <div className="dashboard">
      <DashboardHeader
        analyzedCalls={data?.analyzed_calls ?? 0}
        usableCalls={data?.usable_calls ?? 0}
      />

      <div className="dashboard__toolbar">
        <div className="dashboard__filters">
          <PlantFilter plants={plants} value={plant} onChange={setPlant} />
          <AgentFilter agents={agents} value={agent} onChange={setAgent} />
        </div>
        <SectionNav active={section} onChange={setSection} />
      </div>
      <FilterChips />
      <DataModeBanner />

      {error && (
        <div className="dashboard__banner" role="alert">
          <strong>Can't load the dashboard.</strong> {error}
        </div>
      )}

      {/* The headline numbers stay above the sections, so the big picture is
          on screen whichever group of detail cards is open. */}
      <KpiSummaryStrip data={data} />

      {/* The dashboard is one screen tall (see .app-fit): the open section takes
          whatever height is left and its cards share it. A list longer than its
          card scrolls inside that card, so the page itself never scrolls.
          Filters stay global across sections and show in <FilterChips>. */}
      {section === 'overview' && (
        <div className="dashboard__section dashboard__section--two">
          <ExecutiveSummary data={data} error={error} filters={filters} />
          <KeyInsights />
        </div>
      )}

      {section === 'customers' && (
        <div className="dashboard__section dashboard__section--three">
          <SentimentOverview />
          <SatisfactionRating />
          <TrendComparison data={data} error={error} />
        </div>
      )}

      {section === 'quality' && (
        <div className="dashboard__section dashboard__section--two">
          <CallQualitySummary />
          <CallConnectionSummary />
        </div>
      )}

      {section === 'issues' && (
        <div className="dashboard__section dashboard__section--two">
          <IssueAnalysisTable data={data} error={error} />
          <ServiceIssuesTable data={data} error={error} />
        </div>
      )}

      {section === 'compliance' && (
        <div className="dashboard__section dashboard__section--two">
          <AgentComplianceSummary />
          <ComplianceIssuesTable data={data} error={error} />
        </div>
      )}

      {section === 'agents' && (
        <div className="dashboard__section">
          <AgentPerformanceTable data={data} error={error} />
        </div>
      )}
    </div>
  );
}

function Shell() {
  const { tab, setTab } = useNavigation();
  // Only the dashboard is locked to one screen; Calls and Admin are long
  // lists and forms, so they keep normal page scrolling.
  return (
    <div className={tab === 'dashboard' ? 'app-fit' : undefined}>
      <TabNav active={tab} onChange={setTab} />
      {tab === 'dashboard' && <Dashboard />}
      {tab === 'calls' && <CallsPage />}
      {tab === 'admin' && <AdminPage />}
    </div>
  );
}

function App() {
  return (
    <NavigationProvider>
      <DashboardDataProvider>
        <Shell />
      </DashboardDataProvider>
    </NavigationProvider>
  );
}

export default App;
