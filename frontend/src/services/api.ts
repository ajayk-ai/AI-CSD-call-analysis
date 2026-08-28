const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export interface PipelineRunSummary {
  found_in_bucket: number;
  already_processed: number;
  newly_processed: number;
  failed: number;
  errors: string[];
}

export async function runAnalysisPipeline(): Promise<PipelineRunSummary> {
  const response = await fetch(`${API_BASE_URL}/api/pipeline/run`, { method: 'POST' });
  if (!response.ok) {
    const body = await response.text().catch(() => '');
    throw new Error(`Pipeline run failed (${response.status}): ${body || response.statusText}`);
  }
  return response.json();
}
