import { useCallback, useEffect, useState } from 'react';
import { Card } from '../common/Card';
import {
  fetchDashboardPlants,
  fetchDeepHealth,
  fetchHealth,
  fetchPipelineStatus,
  pingCallsEndpoint,
  type DeepHealthStatus,
} from '../../services/api';
import './EndpointHealthPanel.css';

type CheckResult = { status: 'checking' | 'ok' | 'error'; ms?: number; detail?: string };

interface EndpointDef {
  label: string;
  method: string;
  path: string;
  call: () => Promise<unknown>;
}

// Cheap, side-effect-free GETs only — safe to hit on mount and on demand.
// The deep DB/GCS/Gemini probe is intentionally separate (see below): it
// costs a real Gemini call and a GCS bucket listing, so it's never auto-run.
const ENDPOINTS: EndpointDef[] = [
  { label: 'Health', method: 'GET', path: '/api/health', call: fetchHealth },
  { label: 'Pipeline Status', method: 'GET', path: '/api/pipeline/status', call: fetchPipelineStatus },
  { label: 'Dashboard Plants', method: 'GET', path: '/api/dashboard/plants', call: fetchDashboardPlants },
  { label: 'Calls', method: 'GET', path: '/api/calls?limit=1', call: pingCallsEndpoint },
];

async function checkOne(endpoint: EndpointDef): Promise<CheckResult> {
  const start = performance.now();
  try {
    await endpoint.call();
    return { status: 'ok', ms: Math.round(performance.now() - start) };
  } catch (error) {
    return {
      status: 'error',
      ms: Math.round(performance.now() - start),
      detail: error instanceof Error ? error.message : 'Unknown error',
    };
  }
}

export function EndpointHealthPanel() {
  const [results, setResults] = useState<Record<string, CheckResult>>({});
  const [deep, setDeep] = useState<DeepHealthStatus | null>(null);
  const [deepState, setDeepState] = useState<'idle' | 'running' | 'done' | 'error'>('idle');
  const [deepError, setDeepError] = useState<string | null>(null);

  const runChecks = useCallback(() => {
    setResults(Object.fromEntries(ENDPOINTS.map((e) => [e.label, { status: 'checking' as const }])));
    ENDPOINTS.forEach((endpoint) => {
      checkOne(endpoint).then((result) =>
        setResults((current) => ({ ...current, [endpoint.label]: result })),
      );
    });
  }, []);

  useEffect(() => {
    runChecks();
  }, [runChecks]);

  const runDeepChecks = async () => {
    setDeepState('running');
    setDeepError(null);
    try {
      setDeep(await fetchDeepHealth());
      setDeepState('done');
    } catch (error) {
      setDeepError(error instanceof Error ? error.message : 'Unknown error');
      setDeepState('error');
    }
  };

  return (
    <Card
      title="Endpoint Health"
      subtitle="Live status of the FastAPI routes this dashboard depends on"
      icon="💚"
    >
      <div className="endpoint-health">
        <div className="endpoint-health__toolbar">
          <button type="button" className="endpoint-health__button" onClick={runChecks}>
            ↻ Recheck
          </button>
        </div>

        <table className="endpoint-health__table">
          <thead>
            <tr>
              <th>Endpoint</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Latency</th>
            </tr>
          </thead>
          <tbody>
            {ENDPOINTS.map((endpoint) => {
              const result = results[endpoint.label];
              return (
                <tr key={endpoint.label}>
                  <td>
                    <div className="endpoint-health__name">{endpoint.label}</div>
                    <div className="endpoint-health__path">
                      {endpoint.method} {endpoint.path}
                    </div>
                  </td>
                  <td>
                    <span className={`endpoint-health__dot endpoint-health__dot--${result?.status ?? 'checking'}`} />
                    {result?.status === 'checking' && 'Checking…'}
                    {result?.status === 'ok' && 'Up'}
                    {result?.status === 'error' && (result.detail ?? 'Down')}
                  </td>
                  <td style={{ textAlign: 'right' }}>{result?.ms !== undefined ? `${result.ms} ms` : '—'}</td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <div className="endpoint-health__deep">
          <button
            type="button"
            className="endpoint-health__button"
            onClick={runDeepChecks}
            disabled={deepState === 'running'}
            title="Actually exercises the database, lists the GCS bucket, and makes one Gemini call. Costs a fraction of a cent — not auto-run."
          >
            {deepState === 'running' ? 'Running deep checks…' : '🔎 Run deep checks (DB / GCS / Gemini)'}
          </button>

          {deepState === 'error' && (
            <p className="endpoint-health__deep-error">{deepError}</p>
          )}

          {deep && (
            <ul className="endpoint-health__probes">
              {deep.probes.map((probe) => (
                <li key={probe.name} className={`endpoint-health__probe endpoint-health__probe--${probe.status}`}>
                  <span className={`endpoint-health__dot endpoint-health__dot--${probe.status === 'ok' ? 'ok' : 'error'}`} />
                  <strong>{probe.name}</strong>
                  <span className="endpoint-health__probe-detail">{probe.detail}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}
