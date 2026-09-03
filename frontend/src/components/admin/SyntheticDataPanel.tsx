import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { useDataMode, useDashboardRefresh } from '../../state/dashboardContext';
import {
  clearSyntheticData,
  fetchSyntheticDataStatus,
  generateSyntheticData,
  type DataMode,
  type SyntheticDataStatus,
} from '../../services/api';
import './SyntheticDataPanel.css';

const MIN_COUNT = 5;
const MAX_COUNT = 500;

const MODE_OPTIONS: { key: DataMode; label: string; hint: string }[] = [
  { key: 'live', label: 'Live', hint: 'Real calls only — the normal view.' },
  { key: 'synthetic', label: 'Synthetic', hint: 'Only dummy calls — safe to preview KPI/UI changes with.' },
  { key: 'all', label: 'All', hint: 'Live + synthetic combined.' },
];

/**
 * Cost-free dummy data for QA: generates realistic fake calls entirely on the
 * backend (no GCS listing, no Gemini calls — see synthetic_data_service.py),
 * so the dashboard's KPIs and cards can be exercised without spending
 * anything or touching real data. The Data Mode selector here is the same
 * one every dashboard/Calls-page card reads from (dashboardContext) — switch
 * it to "Synthetic" to preview, then back to "Live" when done.
 */
export function SyntheticDataPanel() {
  const { dataMode, setDataMode } = useDataMode();
  const { refresh } = useDashboardRefresh();
  const [status, setStatus] = useState<SyntheticDataStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [countText, setCountText] = useState(String(50));
  const [busy, setBusy] = useState<'idle' | 'generating' | 'clearing'>('idle');

  const loadStatus = () => {
    fetchSyntheticDataStatus()
      .then(setStatus)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unknown error'));
  };

  useEffect(loadStatus, []);

  const parsedCount = Number(countText);
  const isValid = Number.isInteger(parsedCount) && parsedCount >= MIN_COUNT && parsedCount <= MAX_COUNT;

  const handleGenerate = async () => {
    setBusy('generating');
    setError(null);
    try {
      const result = await generateSyntheticData(parsedCount);
      setStatus(result);
      refresh(); // bump the shared cache so open dashboard/Calls views pick up the new rows
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setBusy('idle');
    }
  };

  const handleClear = async () => {
    setBusy('clearing');
    setError(null);
    try {
      const result = await clearSyntheticData();
      setStatus(result);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setBusy('idle');
    }
  };

  return (
    <Card
      title="Synthetic Data"
      subtitle="Cost-free dummy calls for QA — no GCS or Gemini calls involved"
      icon="🧪"
    >
      <div className="synthetic-data">
        <div className="synthetic-data__mode">
          <span className="synthetic-data__mode-label">Viewing</span>
          <div className="synthetic-data__mode-options" role="tablist" aria-label="Data mode">
            {MODE_OPTIONS.map((option) => (
              <button
                key={option.key}
                type="button"
                role="tab"
                aria-selected={dataMode === option.key}
                title={option.hint}
                className={`synthetic-data__mode-btn ${dataMode === option.key ? 'synthetic-data__mode-btn--active' : ''}`}
                onClick={() => setDataMode(option.key)}
              >
                {option.label}
              </button>
            ))}
          </div>
          {dataMode !== 'live' && (
            <p className="synthetic-data__mode-hint">
              Dashboard and Calls tabs are showing {dataMode === 'all' ? 'live + synthetic' : 'synthetic-only'} data.
              Switch back to "Live" when done.
            </p>
          )}
        </div>

        {error ? (
          <CardState kind="error" message={error} />
        ) : !status ? (
          <CardState kind="loading" />
        ) : (
          <p className="synthetic-data__counts">
            <strong>{status.live_calls}</strong> live calls · <strong>{status.synthetic_calls}</strong> synthetic
            calls
          </p>
        )}

        <div className="synthetic-data__generate">
          <label className="synthetic-data__field">
            Calls to generate
            <input
              type="number"
              min={MIN_COUNT}
              max={MAX_COUNT}
              value={countText}
              onChange={(e) => setCountText(e.target.value)}
            />
          </label>
          <button
            type="button"
            className="synthetic-data__generate-btn"
            onClick={handleGenerate}
            disabled={!isValid || busy !== 'idle'}
          >
            {busy === 'generating' ? 'Generating…' : '+ Generate'}
          </button>
          <button
            type="button"
            className="synthetic-data__clear-btn"
            onClick={handleClear}
            disabled={busy !== 'idle' || !status?.synthetic_calls}
          >
            {busy === 'clearing' ? 'Clearing…' : 'Clear synthetic data'}
          </button>
        </div>
        {!isValid && (
          <p className="synthetic-data__hint">
            Enter a number between {MIN_COUNT} and {MAX_COUNT}.
          </p>
        )}
      </div>
    </Card>
  );
}
