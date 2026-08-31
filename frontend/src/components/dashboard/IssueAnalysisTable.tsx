import { RankedIssuesCard } from './RankedIssuesCard';
import type { DashboardSummary } from '../../services/api';

interface IssueAnalysisTableProps {
  data: DashboardSummary | null;
  error?: string;
}

export function IssueAnalysisTable({ data, error }: IssueAnalysisTableProps) {
  return (
    <RankedIssuesCard
      title="Top Issue Analysis (Negative Drivers)"
      categoryHeader="Issue Category"
      totalLabel="Total Complaint Mentions"
      icon="⚠️"
      variant="red"
      fallbackIcon="🛠️"
      rows={data?.top_negative_drivers ?? []}
      data={data}
      error={error}
      emptyMessage="No complaint drivers recorded yet"
      emptyHint="Categories appear here as the model finds them; the taxonomy grows with each run."
    />
  );
}
