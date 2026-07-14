import type { FedRegime, HistoryAnnotation } from "../api";

interface Props {
  regimes: FedRegime[];
  annotations: HistoryAnnotation[];
}

function formatRange(start: string | null, end: string | null): string {
  const startYear = start ? start.slice(0, 4) : "—";
  const endYear = end ? end.slice(0, 4) : "present";
  return `${startYear}–${endYear}`;
}

// Plain-text, always-visible twin of the chart's regime bands/annotations --
// the chart's hover tooltip isn't reliably keyboard/screen-reader navigable,
// so every value shown as a band on the chart is also reachable here without
// hovering anything.
export default function RegimeLegend({ regimes, annotations }: Props) {
  return (
    <div className="regime-legend">
      <div className="regime-legend-col">
        <h4>Fed Chair eras</h4>
        <ul>
          {regimes.map((r) => (
            <li key={r.chair}>
              <span>{r.chair}</span>
              <span className="muted">{formatRange(r.start, r.end)}</span>
            </li>
          ))}
        </ul>
      </div>
      <div className="regime-legend-col">
        <h4>Data notes</h4>
        <ul>
          {annotations.map((a, i) => (
            <li key={i}>
              <span>{a.label}</span>
              <span className="muted">{formatRange(a.start, a.end)}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
