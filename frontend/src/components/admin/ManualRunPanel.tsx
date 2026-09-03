import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import {
  fetchPipelineStatus,
  runAnalysisPipeline,
  type PipelineRunSummary,
  type PipelineStatus,
} from '../../services/api';
import { useDashboardRefresh } from '../../state/dashboardContext';
import './ManualRunPanel.css';

type RunState = 'idle' | 'running' | 'success' | 'error';

const MIN_LIMIT = 5;

function describe(summary: PipelineRunSummary): string {
  const analyzed = summary.newly_processed - summary.skipped_by_prescreen;
  const parts = [`Analyzed ${analyzed} recording${analyzed === 1 ? '' : 's'}`];
  if (summary.skipped_by_prescreen > 0) {
    parts.push(`${summary.skipped_by_prescreen} skipped as unusable`);
  }
  if (summary.failed > 0) {
    parts.push(`${summary.failed} failed`);
  }
  if (summary.remaining_pending > 0) {
    parts.push(`${summary.remaining_pending} still queued`);
  }
  return `${parts.join(', ')}.`;
}

export function ManualRunPanel() {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [limitText, setLimitText] = useState(String(MIN_LIMIT));
  const [forceReanalyze, setForceReanalyze] = useState(false);
  const [state, setState] = useState<RunState>('idle');
  const [summary, setSummary] = useState<PipelineRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const { refresh } = useDashboardRefresh();

  useEffect(() => {
    fetchPipelineStatus()
      .then((result) => {
        setStatus(result);
        setLimitText(String(result.default_run_limit > 0 ? result.default_run_limit : MIN_LIMIT));
      })
      .catch(() => undefined);
  }, [summary]);

  const parsedLimit = Number(limitText);
  const isUncapped = limitText.trim() === '' || parsedLimit === 0;
  const isValid = isUncapped || (Number.isInteger(parsedLimit) && parsedLimit >= MIN_LIMIT);

  const handleRun = async () => {
    setState('running');
    setErrorMessage(null);
    try {
      const result = await runAnalysisPipeline(isUncapped ? 0 : parsedLimit, forceReanalyze);
      setSummary(result);
      setState('success');
      refresh();
    } catch (error) {
      setErrorMessage(error instanceof Error ? error.message : 'Unknown error');
      setState('error');
    }
  };

  return (
    <Card title="Run Analysis Manually" subtitle="Analyze a specific number of calls right now" icon="▶️">
      <div className="manual-run">
        <label className="manual-run__field">
          Calls to analyze (min {MIN_LIMIT}, 0 = all pending)
          <input
            type="number"
            min={0}
            value={limitText}
            onChange={(e) => setLimitText(e.target.value)}
          />
        </label>
        {!isValid && (
          <p className="manual-run__hint">Enter 0 for uncapped, or at least {MIN_LIMIT}.</p>
        )}

        <label className="manual-run__field manual-run__field--checkbox">
          <input
            type="checkbox"
            checked={forceReanalyze}
            onChange={(e) => setForceReanalyze(e.target.checked)}
          />
          Re-analyze already-processed calls
        </label>
        {forceReanalyze && (
          <p className="manual-run__hint">
            Backfills new analysis fields onto historical calls — costs a Gemini call per call re-analyzed,
            same as the first time.
          </p>
        )}

        <button
          type="button"
          className="manual-run__button"
          onClick={handleRun}
          disabled={state === 'running' || !isValid}
        >
          {state === 'running' ? (
            <>
              <span className="manual-run__spinner" aria-hidden="true" /> Running…
            </>
          ) : (
            <>▶ Run Analysis{isUncapped ? ' (all pending)' : ` (${parsedLimit})`}</>
          )}
        </button>

        {state === 'idle' && status && status.not_yet_analyzed > 0 && (
          <p className="manual-run__status">{status.not_yet_analyzed} recordings queued.</p>
        )}
        {state === 'success' && summary && (
          <p className="manual-run__status manual-run__status--success">{describe(summary)}</p>
        )}
        {state === 'error' && (
          <p className="manual-run__status manual-run__status--error">
            {errorMessage ?? 'Something went wrong.'}
          </p>
        )}
      </div>
    </Card>
  );
}
