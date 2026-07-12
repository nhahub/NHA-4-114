"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { format } from "date-fns";

interface DataPoint {
  timestamp: string;
  occupancy: number;
}

interface OccupancyChartProps {
  data: DataPoint[];
  height?: number;
}

function CustomTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-surface-600 border border-border rounded px-3 py-2 shadow-panel">
      <p className="text-ink-secondary text-xs font-mono mb-1">{label}</p>
      <p className="text-accent text-sm font-mono">
        {payload[0].value} persons
      </p>
    </div>
  );
}

export default function OccupancyChart({
  data,
  height = 200,
}: OccupancyChartProps) {
  const formatted = data.map((d) => ({
    ...d,
    time: format(new Date(d.timestamp), "HH:mm"),
  }));

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={formatted} margin={{ top: 8, right: 8, bottom: 0, left: -20 }}>
        <CartesianGrid
          strokeDasharray="3 3"
          stroke="#1C2733"
          vertical={false}
        />
        <XAxis
          dataKey="time"
          tick={{ fill: "#8B95A3", fontSize: 10, fontFamily: "JetBrains Mono" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tick={{ fill: "#8B95A3", fontSize: 10, fontFamily: "JetBrains Mono" }}
          axisLine={false}
          tickLine={false}
          allowDecimals={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Line
          type="monotone"
          dataKey="occupancy"
          stroke="#00D4FF"
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 4, fill: "#00D4FF", stroke: "#080C12", strokeWidth: 2 }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}
