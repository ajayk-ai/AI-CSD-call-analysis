import { RankedIssuesCard } from './RankedIssuesCard';
import type { DashboardSummary } from '../../services/api';

interface ServiceIssuesTableProps {
  data: DashboardSummary | null;
  error?: string;
}

export function ServiceIssuesTable({ data, error }: ServiceIssuesTableProps) {
  return (
    <RankedIssuesCard
      title="Top Service / Machine Issues Reported"
      categoryHeader="Service / Machine Issue"
      totalLabel="Total Issue Mentions"
      icon="🛠️"
      variant="blue"
      fallbackIcon="🔧"
      rows={data?.top_service_issues ?? []}
      data={data}
      error={error}
      emptyMessage="No machine issues recorded yet"
      emptyHint="Mechanical and technical problems mentioned on calls are ranked here."
    />
  );
}
