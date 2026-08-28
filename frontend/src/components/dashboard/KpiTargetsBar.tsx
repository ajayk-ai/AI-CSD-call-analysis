import { Card } from '../common/Card';
import type { KpiTarget } from '../../types/dashboard.types';
import './KpiTargetsBar.css';

interface KpiTargetsBarProps {
  targets: KpiTarget[];
}

export function KpiTargetsBar({ targets }: KpiTargetsBarProps) {
  return (
    <Card title="Customer Care KPI Targets" icon="🎯">
      <div className="kpi-bar">
        {targets.map((target) => (
          <div key={target.label} className="kpi-bar__tile">
            <span className="kpi-bar__icon">{target.icon}</span>
            <span className="kpi-bar__label">{target.label}</span>
            <span className="kpi-bar__value">{target.value}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}
