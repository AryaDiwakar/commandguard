import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { TelemetryFrame } from "../lib/types";
import { Panel } from "./Panel";

export interface SeriesDef {
  key: keyof TelemetryFrame;
  color: string;
  domain: [number, number];
  unit?: string;
  fitToData?: boolean;
}

export function TeleChart({
  title,
  frames,
  series,
  height = 120,
}: {
  title: string;
  frames: TelemetryFrame[];
  series: SeriesDef[];
  height?: number;
}) {
  const data = frames.slice(-180).map((f, i) => {
    const row: Record<string, string | number> = { t: i };
    for (const s of series) row[s.key] = Number(f[s.key]) || 0;
    return row;
  });
  const firstSeries = series[0];
  const yDomain = firstSeries?.fitToData && data.length
    ? (() => {
        const values = data.map((row) => Number(row[String(firstSeries.key)])).filter(Number.isFinite);
        const low = Math.min(...values);
        const high = Math.max(...values);
        const padding = Math.max(0.5, (high - low) * 0.25);
        return [Math.max(firstSeries.domain[0], low - padding), Math.min(firstSeries.domain[1], high + padding)] as [number, number];
      })()
    : firstSeries?.domain ?? [0, 100];

  return (
    <Panel title={title}>
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={data} margin={{ top: 4, right: 4, bottom: 0, left: -14 }}>
          <CartesianGrid stroke="#1a2432" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="t" hide />
          <YAxis
            domain={yDomain}
            tick={{ fill: "#64748b", fontSize: 10 }}
            tickFormatter={(v: number) => String(v)}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: "#0a0f17",
              border: "1px solid #223040",
              borderRadius: 8,
              fontSize: 11,
            }}
            labelStyle={{ color: "#94a3b8" }}
          />
          {series.map((s) => (
            <Line
              key={String(s.key)}
              type="monotone"
              dataKey={String(s.key)}
              stroke={s.color}
              strokeWidth={1.6}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </Panel>
  );
}
