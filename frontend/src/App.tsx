import './App.css';
import { DashboardHeader } from './components/layout/DashboardHeader';
import { CallQualitySummary } from './components/dashboard/CallQualitySummary';
import { SentimentOverview } from './components/dashboard/SentimentOverview';
import { SatisfactionRating } from './components/dashboard/SatisfactionRating';
import { TrendComparison } from './components/dashboard/TrendComparison';
import { IssueAnalysisTable } from './components/dashboard/IssueAnalysisTable';
import { ServiceIssuesTable } from './components/dashboard/ServiceIssuesTable';
import { dashboardData } from './data/mockData';

function App() {
  const data = dashboardData;

  return (
    <div className="dashboard">
      <DashboardHeader totalCalls={data.totalCallsAnalyzed} />

      <div className="dashboard__row dashboard__row--four">
        <CallQualitySummary byRange={data.callQualityByRange} />
        <SentimentOverview byRange={data.sentimentByRange} />
        <SatisfactionRating
          rows={data.satisfaction}
          usableCalls={data.usableCalls}
          averageRating={data.averageRating}
        />
        <TrendComparison monthlyAverages={data.monthlyAverages} dailyRatings={data.dailyRatings} />
      </div>

      <div className="dashboard__row dashboard__row--two">
        <IssueAnalysisTable rows={data.topIssues} usableCalls={data.usableCalls} />
        <ServiceIssuesTable rows={data.topServiceIssues} usableCalls={data.usableCalls} />
      </div>
    </div>
  );
}

export default App;
