import { EndpointHealthPanel } from '../components/admin/EndpointHealthPanel';
import { SchedulePanel } from '../components/admin/SchedulePanel';
import { ManualRunPanel } from '../components/admin/ManualRunPanel';
import { KpiFlowPanel } from '../components/admin/KpiFlowPanel';
import { SyntheticDataPanel } from '../components/admin/SyntheticDataPanel';
import './AdminPage.css';

export function AdminPage() {
  return (
    <div className="admin-page">
      <header className="admin-page__header">
        <h1 className="admin-page__title">Admin</h1>
        <p className="admin-page__subtitle">
          Endpoint health, the analysis flow, and scheduled or manual runs
        </p>
      </header>

      <div className="admin-page__row">
        <EndpointHealthPanel />
        <SchedulePanel />
      </div>
      <div className="admin-page__row admin-page__row--single">
        <KpiFlowPanel />
      </div>
      <div className="admin-page__row admin-page__row--single">
        <ManualRunPanel />
      </div>
      <div className="admin-page__row admin-page__row--single">
        <SyntheticDataPanel />
      </div>
    </div>
  );
}
