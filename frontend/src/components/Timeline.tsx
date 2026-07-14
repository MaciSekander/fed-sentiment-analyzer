import { useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { HistoryResponse } from "../api";

interface Props {
  history: HistoryResponse;
}

function toTs(date: string | null): number | null {
  return date ? Date.parse(`${date}T00:00:00Z`) : null;
}

function chairLastName(chair: string): string {
  return chair.split(" ").slice(-1)[0];
}

interface ChartPoint {
  ts: number;
  score: number | null;
  rolling: number | null;
  label: string | null;
  chair: string | null;
  doc_id: string | null;
}

function TimelineTooltip({ active, payload }: { active?: boolean; payload?: { payload: ChartPoint }[] }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  if (point.score === null) return null;
  return (
    <div className="timeline-tooltip">
      <div className="timeline-tooltip-date">{new Date(point.ts).toISOString().slice(0, 10)}</div>
      {point.chair && <div className="muted">{point.chair}</div>}
      <div className={`label-${point.label ?? "neutral"}`}>
        score {point.score.toFixed(3)} ({point.label})
      </div>
    </div>
  );
}

export default function Timeline({ history }: Props) {
  const chartData = useMemo<ChartPoint[]>(
    () =>
      history.points.map((p) => ({
        ts: toTs(p.date) ?? 0,
        score: p.combined_score,
        rolling: p.combined_score_rolling,
        label: p.combined_label,
        chair: p.chair,
        doc_id: p.doc_id,
      })),
    [history.points],
  );

  const domain = useMemo<[number, number]>(() => {
    const dataTs = chartData.map((d) => d.ts).filter((t) => t > 0);
    const regimeTs = history.regimes.flatMap((r) => {
      const start = toTs(r.start);
      const end = r.end ? toTs(r.end) : Date.now();
      return [start, end].filter((t): t is number => t !== null);
    });
    const all = [...dataTs, ...regimeTs];
    return [Math.min(...all), Math.max(...all)];
  }, [chartData, history.regimes]);

  const gradientOffset = useMemo(() => {
    const values = chartData.map((d) => d.rolling).filter((v): v is number => v !== null);
    const dataMax = Math.max(0, ...values);
    const dataMin = Math.min(0, ...values);
    if (dataMax <= 0) return 0;
    if (dataMin >= 0) return 1;
    return dataMax / (dataMax - dataMin);
  }, [chartData]);

  return (
    <div className="timeline">
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 12, left: -8, bottom: 0 }}>
          <defs>
            <linearGradient id="rollingFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset={gradientOffset} style={{ stopColor: "var(--hawkish)", stopOpacity: 0.18 }} />
              <stop offset={gradientOffset} style={{ stopColor: "var(--dovish)", stopOpacity: 0.18 }} />
            </linearGradient>
          </defs>

          <CartesianGrid stroke="var(--border)" vertical={false} />

          {history.regimes.map((r, i) => {
            const x1 = toTs(r.start);
            const x2 = r.end ? toTs(r.end) : Date.now();
            if (x1 === null || x2 === null) return null;
            return (
              <ReferenceArea
                key={r.chair}
                x1={x1}
                x2={x2}
                y1={-1}
                y2={1}
                fill={i % 2 === 0 ? "var(--panel)" : "transparent"}
                fillOpacity={0.6}
                label={{ value: chairLastName(r.chair), position: "insideTop", fill: "var(--muted)", fontSize: 10 }}
              />
            );
          })}

          {history.annotations.map((a, i) => {
            const x1 = a.start ? toTs(a.start) : domain[0];
            const x2 = a.end ? toTs(a.end) : domain[1];
            if (x1 === null || x2 === null) return null;
            return (
              <ReferenceArea
                key={`annotation-${i}`}
                x1={x1}
                x2={x2}
                y1={-1}
                y2={1}
                fill="var(--muted)"
                fillOpacity={0.16}
                label={{ value: a.label, position: "insideBottom", fill: "var(--muted)", fontSize: 10 }}
              />
            );
          })}

          <ReferenceLine y={0} stroke="var(--muted)" strokeWidth={1} />

          <XAxis
            dataKey="ts"
            type="number"
            domain={domain}
            tickFormatter={(ts) => new Date(ts).getUTCFullYear().toString()}
            stroke="var(--border)"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
          />
          <YAxis
            domain={[-1, 1]}
            ticks={[-1, -0.5, 0, 0.5, 1]}
            stroke="var(--border)"
            tick={{ fill: "var(--muted)", fontSize: 11 }}
            width={40}
          />

          <Area
            type="monotone"
            dataKey="rolling"
            stroke="none"
            fill="url(#rollingFill)"
            connectNulls={false}
            isAnimationActive={false}
            legendType="none"
          />
          <Line
            type="monotone"
            dataKey="score"
            stroke="var(--muted)"
            strokeWidth={1}
            strokeOpacity={0.6}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
            name="Per-document score"
          />
          <Line
            type="monotone"
            dataKey="rolling"
            stroke="var(--text)"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
            isAnimationActive={false}
            name={`${history.window}-doc rolling average`}
          />

          <Tooltip content={<TimelineTooltip />} />
          <Legend verticalAlign="top" height={28} wrapperStyle={{ fontSize: 12, color: "var(--muted)" }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
