import { useMemo } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { FedFundsResponse } from "../api";
import { HISTORY_CHART_SYNC_ID, parseDateToTs as toTs } from "../lib/chartTime";

interface Props {
  fedFunds: FedFundsResponse;
  domain: [number, number];
}

interface ChartPoint {
  ts: number;
  rate: number;
}

function FedFundsTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="timeline-tooltip">
      <div className="timeline-tooltip-date">{new Date(point.ts).toISOString().slice(0, 10)}</div>
      <div>{point.rate.toFixed(2)}%</div>
    </div>
  );
}

// A single, independent measure -- effective Fed funds rate, from FRED --
// shown as its own small-multiples panel below Timeline rather than
// overlaid on it, since the two are different units/scale (percent vs. a
// -1..1 sentiment score) and combining them on one axis would be
// misleading. Sharing HISTORY_CHART_SYNC_ID with Timeline gives a synced
// hover crosshair between the two panels.
export default function FedFundsChart({ fedFunds, domain }: Props) {
  const chartData = useMemo<ChartPoint[]>(
    () => fedFunds.points.map((p) => ({ ts: toTs(p.date) ?? 0, rate: p.rate })),
    [fedFunds.points],
  );
  const lastIndex = chartData.length - 1;

  // Recharts' Line label-render props type isn't easily named from the
  // outside (varies with the chart's generics) -- read defensively instead.
  function endLabel(props: unknown) {
    const { index, x, y, value } = props as { index?: number; x?: number | string; y?: number | string; value?: number };
    if (index !== lastIndex || x === undefined || y === undefined || value === undefined) {
      return <g key="fedfunds-end-label" />;
    }
    return (
      <text
        key="fedfunds-end-label"
        x={Number(x) + 6}
        y={Number(y)}
        dy={4}
        fill="var(--text)"
        fontSize={11}
        textAnchor="start"
      >
        {value.toFixed(2)}%
      </text>
    );
  }

  return (
    <div className="fedfunds-chart">
      <p className="chart-caption">
        Effective federal funds rate, monthly &middot; source: {fedFunds.source}
      </p>
      <ResponsiveContainer width="100%" height={160}>
        <ComposedChart
          data={chartData}
          margin={{ top: 4, right: 48, left: -8, bottom: 0 }}
          syncId={HISTORY_CHART_SYNC_ID}
          syncMethod="value"
        >
          <CartesianGrid stroke="var(--border)" vertical={false} />
          <XAxis
            dataKey="ts"
            type="number"
            domain={domain}
            tickFormatter={(ts) => new Date(ts).getUTCFullYear().toString()}
            stroke="var(--border)"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
          />
          <YAxis
            stroke="var(--border)"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            width={40}
            tickFormatter={(v) => `${v}%`}
          />
          <Line
            type="monotone"
            dataKey="rate"
            stroke="var(--text)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
            connectNulls={false}
            label={endLabel}
          />
          <Tooltip content={<FedFundsTooltip />} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
