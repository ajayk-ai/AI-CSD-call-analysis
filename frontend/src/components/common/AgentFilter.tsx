import './AgentFilter.css';

interface AgentFilterProps {
  /** Every known agent name — dynamic, not hardcoded (see GET /api/dashboard/agents). */
  agents: string[];
  value: string | null;
  onChange: (agent: string | null) => void;
}

/**
 * Global agent filter — one selection drives every KPI card on the
 * dashboard (see dashboardContext's `agent`), the same way PlantFilter
 * already does for plant. A dropdown rather than PlantFilter's button row:
 * plants only ever have a couple of values, agent rosters can run into the
 * dozens.
 */
export function AgentFilter({ agents, value, onChange }: AgentFilterProps) {
  if (agents.length === 0) return null;

  return (
    <div className="agent-filter">
      <span className="agent-filter__label">Agent</span>
      <select
        className="agent-filter__select"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value || null)}
        aria-label="Filter dashboard by agent"
      >
        <option value="">All Agents</option>
        {agents.map((agent) => (
          <option key={agent} value={agent}>
            {agent}
          </option>
        ))}
      </select>
      {value && (
        <button type="button" className="agent-filter__clear" onClick={() => onChange(null)} title="Clear agent filter">
          ×
        </button>
      )}
    </div>
  );
}
