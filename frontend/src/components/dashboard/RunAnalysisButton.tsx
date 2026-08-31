import { useEffect, useState } from 'react';
import {
  configuredRunLimit,
  fetchPipelineStatus,
  runAnalysisPipeline,
  type PipelineRunSummary,
  type PipelineStatus,
} from '../../services/api';
import { useDashboardRefresh } from '../../state/dashboardContext';
import './RunAnalysisButton.css';

type RunState = 'idle' | 'running' | 'success' | 'error';

function describe(summary: PipelineRunSummary): string {
  const analyzed = summary.newly_processed - summary.skipped_by_prescreen;
  const parts = [`Analyzed ${analyzed} recording${analyzed === 1 ? '' : 's'}`];

  if (summary.skipped_by_prescreen > 0) {
    parts.push(`${summary.skipped_by_prescreen} skipped as unusable (no model cost)`);
  }
  if (summary.failed > 0) {
    parts.push(`${summary.failed} failed`);
  }
  if (summary.remaining_pending > 0) {
    parts.push(`${summary.remaining_pending} still queued — click again for the next batch`);
  }
  return `${parts.join(', ')}.`;
}

export function RunAnalysisButton() {
  const [state, setState] = useState<RunState>('idle');
  const [summary, setSummary] = useState<PipelineRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const { refresh } = useDashboardRefresh();

  // Backend's configured limit is the source of truth for the label; the
  // frontend override only matters if VITE_PIPELINE_LIMIT is set.
  const limit = configuredRunLimit() ?? (status && status.default_run_limit > 0 ? status.default_run_limit : null);

  useEffect(() => {
    fetchPipelineStatus()
      .then(setStatus)
      // A failure here only costs the button its subtitle — the run itself
      // reports its own errors, so there's nothing useful to show twice.
      .catch(() => undefined);
  }, [summary]);

  const handleClick = async () => {
    setState('running');
    setErrorMessage(null);
    try {
      const result = await runAnalysisPipeline();
      setSummary(result);
      setState('success');
      // The pipeline changes every panel on the page, so invalidate all of it.
      refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unknown error');
      setState('error');
    }
  };

  return (
    <div className="run-analysis">
      <button
        type="button"
        className="run-analysis__button"
        onClick={handleClick}
        disabled={state === 'running'}
        title={
          limit
            ? `Sends up to ${limit} recordings to Gemini per click. Unusable audio is filtered out first, free.`
            : 'Processes every recording not yet analyzed.'
        }
      >
        {state === 'running' ? (
          <>
            <span className="run-analysis__spinner" aria-hidden="true" />
            Running…
          </>
        ) : (
          <>▶ Run Analysis{limit ? ` (next ${limit})` : ''}</>
        )}
      </button>

      {state === 'running' && (
        <p className="run-analysis__status">
          Transcribing and scoring — this takes a few seconds per recording.
        </p>
      )}
      {state === 'idle' && status && status.not_yet_analyzed > 0 && (
        <p className="run-analysis__status">{status.not_yet_analyzed} recordings queued.</p>
      )}
      {state === 'success' && summary && (
        <p className="run-analysis__status run-analysis__status--success">{describe(summary)}</p>
      )}
      {state === 'error' && (
        <p className="run-analysis__status run-analysis__status--error">
          {errorMessage ?? 'Something went wrong.'}
        </p>
      )}
    </div>
  );
}
