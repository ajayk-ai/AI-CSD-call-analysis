import { useState } from 'react';
import { runAnalysisPipeline, type PipelineRunSummary } from '../../services/api';
import './RunAnalysisButton.css';

type RunState = 'idle' | 'running' | 'success' | 'error';

export function RunAnalysisButton() {
  const [state, setState] = useState<RunState>('idle');
  const [summary, setSummary] = useState<PipelineRunSummary | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleClick = async () => {
    setState('running');
    setErrorMessage(null);
    try {
      const result = await runAnalysisPipeline();
      setSummary(result);
      setState('success');
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
      >
        {state === 'running' ? (
          <>
            <span className="run-analysis__spinner" aria-hidden="true" />
            Running…
          </>
        ) : (
          <>▶ Run Analysis</>
        )}
      </button>
      {state === 'success' && summary && (
        <p className="run-analysis__status run-analysis__status--success">
          Processed {summary.newly_processed} new
          {summary.failed > 0 ? `, ${summary.failed} failed` : ''} — {summary.already_processed} already up to date.
        </p>
      )}
      {state === 'error' && (
        <p className="run-analysis__status run-analysis__status--error">
          {errorMessage ?? 'Something went wrong.'} Is the backend running on localhost:8000?
        </p>
      )}
    </div>
  );
}
