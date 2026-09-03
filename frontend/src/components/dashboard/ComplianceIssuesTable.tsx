import { RankedIssuesCard } from './RankedIssuesCard';
import type { DashboardSummary } from '../../services/api';

interface ComplianceIssuesTableProps {
  data: DashboardSummary | null;
  error?: string;
}

export function ComplianceIssuesTable({ data, error }: ComplianceIssuesTableProps) {
  return (
    <RankedIssuesCard
      title="Top Agent Compliance Issues"
      categoryHeader="Compliance Issue"
      totalLabel="Total Compliance Mentions"
      icon="📋"
      variant="teal"
      fallbackIcon="🧑‍💼"
      rows={data?.top_compliance_issues ?? []}
      data={data}
      error={error}
      emptyMessage="No compliance issues recorded yet"
      emptyHint="Script deviations, topic drift and irrelevant talk are ranked here as the model finds them."
    />
  );
}
