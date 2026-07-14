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
import { HISTORY_CHART_SYNC_ID, parseDateToTs as toTs } from "../lib/chartTime";

interface Props {
  history: HistoryResponse;
  domain: [number, number];
  onSelectDocument?: (docId: string) => void;
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
      {point.doc_id && <div className="timeline-tooltip-hint">Click to read the source document</div>}
    </div>
  );
}

export default function Timeline({ history, domain, onSelectDocument }: Props) {
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

  // The chart-level onClick event (via activeTooltipIndex/activePayload)
  // turned out to be unreliable in this Recharts version -- confirmed
  // empirically with a real headless-browser click that it fires with
  // stale/null state (a race against the hover-state update), flaky
  // roughly 2 times out of 3. It also structurally can't work on touch
  // devices at all, since there's no hover phase before a tap. A real,
  // independent SVG element per point sidesteps both problems entirely --
  // it's a native click/tap target, not dependent on chart-wide gesture
  // state being in sync.
  function renderClickableDot(props: { cx?: number; cy?: number; payload?: ChartPoint }) {
    const { cx, cy, payload } = props;
    if (cx === undefined || cy === undefined || !payload?.doc_id || !onSelectDocument) {
      return <g key={`dot-${payload?.ts ?? cx}`} />;
    }
    const docId = payload.doc_id;
    return (
      <circle
        key={`dot-${docId}`}
        className="timeline-point"
        cx={cx}
        cy={cy}
        r={7}
        fill="transparent"
        pointerEvents="all"
        style={{ cursor: "pointer" }}
        onClick={() => onSelectDocument(docId)}
      />
    );
  }

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
        <ComposedChart
          data={chartData}
          margin={{ top: 8, right: 12, left: -8, bottom: 0 }}
          syncId={HISTORY_CHART_SYNC_ID}
          syncMethod="value"
        >
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
            dot={renderClickableDot}
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
