import { useDataMode } from '../../state/dashboardContext';
import './DataModeBanner.css';

/** Shown on the Dashboard/Calls tabs whenever the global Data Mode (set from
 *  Admin's Synthetic Data panel) isn't "live" — a guard against mistaking
 *  synthetic QA data for real numbers. */
export function DataModeBanner() {
  const { dataMode, setDataMode } = useDataMode();
  if (dataMode === 'live') return null;

  return (
    <div className="data-mode-banner" role="status">
      🧪 Showing {dataMode === 'all' ? 'live + synthetic' : 'synthetic-only'} data — set in Admin → Synthetic Data.
      <button type="button" onClick={() => setDataMode('live')}>
        Switch to Live
      </button>
    </div>
  );
}
