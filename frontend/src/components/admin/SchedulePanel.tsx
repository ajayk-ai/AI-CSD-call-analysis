import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { fetchScheduleConfig, updateScheduleConfig, type ScheduleConfig } from '../../services/api';
import './SchedulePanel.css';

function pad(n: number): string {
  return n.toString().padStart(2, '0');
}

/** Client-computed, informational only — the backend's own APScheduler job
 *  is the source of truth for when it actually fires. */
function describeNextRun(hour: number, minute: number): string {
  const now = new Date();
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
  if (next <= now) next.setDate(next.getDate() + 1);
  const isToday = next.getDate() === now.getDate();
  return `Next run: ${isToday ? 'today' : 'tomorrow'} at ${pad(hour)}:${pad(minute)}`;
}

export function SchedulePanel() {
  const [config, setConfig] = useState<ScheduleConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');

  // Draft form fields, seeded from `config` once it loads.
  const [enabled, setEnabled] = useState(false);
  const [hour, setHour] = useState(7);
  const [minute, setMinute] = useState(0);
  const [limitText, setLimitText] = useState('');

  useEffect(() => {
    fetchScheduleConfig()
      .then((result) => {
        setConfig(result);
        setEnabled(result.enabled);
        setHour(result.run_hour);
        setMinute(result.run_minute);
        setLimitText(result.run_limit === null ? '' : String(result.run_limit));
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, []);

  const handleSave = async () => {
    setSaveState('saving');
    try {
      const run_limit = limitText.trim() === '' ? null : Math.max(0, Number(limitText));
      const result = await updateScheduleConfig({ enabled, run_hour: hour, run_minute: minute, run_limit });
      setConfig(result);
      setSaveState('saved');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setSaveState('error');
    }
  };

  return (
    <Card
      title="Automatic Morning Analysis"
      subtitle="Runs the pipeline on a daily schedule, in the background"
      icon="⏰"
    >
      {error && !config ? (
        <CardState kind="error" message={error} />
      ) : !config ? (
        <CardState kind="loading" />
      ) : (
        <div className="schedule-panel">
          <label className="schedule-panel__toggle">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
            Run automatically every day
          </label>

          <div className="schedule-panel__row">
            <label className="schedule-panel__field">
              Time
              <div className="schedule-panel__time">
                <input
                  type="number"
                  min={0}
                  max={23}
                  value={hour}
                  onChange={(e) => setHour(Math.min(23, Math.max(0, Number(e.target.value))))}
                />
                <span>:</span>
                <input
                  type="number"
                  min={0}
                  max={59}
                  value={minute}
                  onChange={(e) => setMinute(Math.min(59, Math.max(0, Number(e.target.value))))}
                />
              </div>
            </label>

            <label className="schedule-panel__field">
              Calls per run
              <input
                type="number"
                min={0}
                placeholder="uncapped"
                value={limitText}
                onChange={(e) => setLimitText(e.target.value)}
              />
            </label>
          </div>

          {enabled && <p className="schedule-panel__next">{describeNextRun(hour, minute)}</p>}

          <button
            type="button"
            className="schedule-panel__save"
            onClick={handleSave}
            disabled={saveState === 'saving'}
          >
            {saveState === 'saving' ? 'Saving…' : 'Save schedule'}
          </button>

          {saveState === 'saved' && <p className="schedule-panel__status schedule-panel__status--ok">Saved.</p>}
          {saveState === 'error' && (
            <p className="schedule-panel__status schedule-panel__status--error">{error}</p>
          )}

          <div className="schedule-panel__last-run">
            <h3>Last run</h3>
            {config.last_run_at ? (
              <>
                <p>
                  {new Date(config.last_run_at).toLocaleString()} —{' '}
                  <span
                    className={
                      config.last_run_status === 'success'
                        ? 'schedule-panel__status--ok'
                        : 'schedule-panel__status--error'
                    }
                  >
                    {config.last_run_status}
                  </span>
                </p>
                {config.last_run_summary && <p className="schedule-panel__summary">{config.last_run_summary}</p>}
              </>
            ) : (
              <p className="schedule-panel__summary">Never run yet.</p>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
