import { useEffect, useState } from 'react';
import { Card } from '../common/Card';
import { CardState } from '../common/CardState';
import { fetchKpiNodes, updateKpiNode, type KpiNode } from '../../services/api';
import './KpiFlowPanel.css';

const TIER_META: Record<KpiNode['tier'], { badge: string; hint: string; className: string }> = {
  transcription: {
    badge: 'AUDIO',
    hint: 'Reads the recording itself, on the stronger model. Runs once per call and is checkpointed.',
    className: 'kpi-flow__tier--audio',
  },
  extraction: {
    badge: 'TEXT',
    hint: 'Reads the transcript the step above produced, on the cheapest model. No audio cost.',
    className: 'kpi-flow__tier--text',
  },
};

/**
 * The analysis flow, and the one control over it.
 *
 * Each row is a node of the LangGraph pipeline, read straight from the backend
 * registry (app/pipeline/kpi_registry.py) rather than listed here — so a KPI
 * added there shows up on this page with no frontend change at all, which is
 * the point of the registry.
 *
 * The toggles are cheap to use precisely because of the checkpointer: turning
 * a KPI on doesn't mean re-transcribing anything, so experimenting with what
 * the dashboard measures is a text-model cost, not an audio one. The copy
 * below says so, because that's not obvious from a switch.
 */
export function KpiFlowPanel() {
  const [nodes, setNodes] = useState<KpiNode[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);

  useEffect(() => {
    fetchKpiNodes()
      .then(setNodes)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Unknown error'));
  }, []);

  const handleToggle = async (node: KpiNode) => {
    setPending(node.key);
    setError(null);
    try {
      const updated = await updateKpiNode(node.key, !node.enabled);
      setNodes((current) =>
        (current ?? []).map((item) => (item.key === updated.key ? updated : item)),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setPending(null);
    }
  };

  return (
    <Card
      title="Analysis Flow (KPIs)"
      subtitle="What each call is analyzed for, and on which model"
      icon="🧩"
    >
      {error ? (
        <CardState kind="error" message={error} />
      ) : !nodes ? (
        <CardState kind="loading" />
      ) : (
        <div className="kpi-flow">
          <ol className="kpi-flow__list">
            {nodes.map((node, index) => (
              <li
                key={node.key}
                className={`kpi-flow__node ${node.enabled ? '' : 'kpi-flow__node--off'}`}
              >
                <span className="kpi-flow__step">{index + 1}</span>
                <div className="kpi-flow__body">
                  <div className="kpi-flow__heading">
                    <span className="kpi-flow__label">{node.label}</span>
                    <span
                      className={`kpi-flow__tier ${TIER_META[node.tier].className}`}
                      title={TIER_META[node.tier].hint}
                    >
                      {TIER_META[node.tier].badge}
                    </span>
                    <code className="kpi-flow__model">{node.model}</code>
                    <span className="kpi-flow__version">{node.version}</span>
                  </div>
                  <p className="kpi-flow__description">{node.description}</p>
                </div>
                <label className="kpi-flow__switch">
                  <input
                    type="checkbox"
                    checked={node.enabled}
                    disabled={node.required || pending === node.key}
                    onChange={() => handleToggle(node)}
                  />
                  <span>
                    {node.required ? 'Always on' : node.enabled ? 'On' : 'Off'}
                  </span>
                </label>
              </li>
            ))}
          </ol>
          <p className="kpi-flow__note">
            Only step 1 reads the audio, and its result is checkpointed per call. So switching a KPI
            on and then running with <strong>"Re-analyze already-processed calls"</strong> recomputes
            just that step from the stored transcript — no recording is downloaded or sent again.
          </p>
        </div>
      )}
    </Card>
  );
}
