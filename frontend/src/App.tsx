import './App.css';
import { PlantFilter } from './components/common/PlantFilter';
import { DashboardHeader } from './components/layout/DashboardHeader';
import { CallQualitySummary } from './components/dashboard/CallQualitySummary';
import { SentimentOverview } from './components/dashboard/SentimentOverview';
import { SatisfactionRating } from './components/dashboard/SatisfactionRating';
import { TrendComparison } from './components/dashboard/TrendComparison';
import { IssueAnalysisTable } from './components/dashboard/IssueAnalysisTable';
import { ServiceIssuesTable } from './components/dashboard/ServiceIssuesTable';
import { displayData, usePlantFilter, useDashboardSummary } from './state/dashboardContext';
import { DashboardDataProvider } from './state/dashboardData';

/**
 * The two donut cards carry their own time filter and fetch their own range.
 * Everything else reads the "all" summary, which is what this component holds.
 * The plant filter is global (one selection for the whole page) and every
 * `useDashboardSummary` call picks it up automatically via context, so
 * selecting a plant here re-filters every card without passing it down.
 */
function Dashboard() {
  const state = useDashboardSummary('all');
  const data = displayData(state);
  const error = state.status === 'error' ? state.message : undefined;
  const { plant, setPlant, plants } = usePlantFilter();

  return (
    <div className="dashboard">
      <DashboardHeader
        analyzedCalls={data?.analyzed_calls ?? 0}
        usableCalls={data?.usable_calls ?? 0}
      />

      <PlantFilter plants={plants} value={plant} onChange={setPlant} />

      {error && (
        <div className="dashboard__banner" role="alert">
          <strong>Can't load the dashboard.</strong> {error}
        </div>
      )}

      <div className="dashboard__row dashboard__row--four">
        <CallQualitySummary />
        <SentimentOverview />
        <SatisfactionRating data={data} error={error} />
        <TrendComparison data={data} error={error} />
      </div>

      <div className="dashboard__row dashboard__row--two">
        <IssueAnalysisTable data={data} error={error} />
        <ServiceIssuesTable data={data} error={error} />
      </div>
    </div>
  );
}

function App() {
  return (
    <DashboardDataProvider>
      <Dashboard />
    </DashboardDataProvider>
  );
}

export default App;
