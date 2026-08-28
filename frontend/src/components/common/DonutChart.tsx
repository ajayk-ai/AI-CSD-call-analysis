import { Cell, Pie, PieChart } from 'recharts';
import './DonutChart.css';

export interface DonutDatum {
  label: string;
  value: number;
  color: string;
}

interface DonutChartProps {
  data: DonutDatum[];
  centerLabel?: string;
  centerValue?: string;
  size?: number;
}

export function DonutChart({ data, centerLabel, centerValue, size = 180 }: DonutChartProps) {
  return (
    <div
      className="donut-chart"
      style={{ position: 'relative', width: size, height: size, flexShrink: 0 }}
    >
      <PieChart width={size} height={size}>
        <Pie
          data={data}
          dataKey="value"
          nameKey="label"
          innerRadius="62%"
          outerRadius="95%"
          paddingAngle={2}
          stroke="none"
          isAnimationActive={false}
        >
          {data.map((entry) => (
            <Cell key={entry.label} fill={entry.color} />
          ))}
        </Pie>
      </PieChart>
      {(centerLabel || centerValue) && (
        <div className="donut-chart__center">
          {centerValue && <span className="donut-chart__value">{centerValue}</span>}
          {centerLabel && <span className="donut-chart__label">{centerLabel}</span>}
        </div>
      )}
    </div>
  );
}
