interface Props {
  score: number; // -1..1
  label: string;
}

export default function ScoreGauge({ score, label }: Props) {
  const clamped = Math.max(-1, Math.min(1, score));
  const pct = ((clamped + 1) / 2) * 100;

  return (
    <div className="score-gauge">
      <div className={`score-gauge-label label-${label}`}>{label.toUpperCase()}</div>
      <div className="score-gauge-track">
        <div className="score-gauge-tick" style={{ left: "25%" }} />
        <div className="score-gauge-midline" />
        <div className="score-gauge-tick" style={{ left: "75%" }} />
        <div className="score-gauge-marker" style={{ left: `${pct}%` }} />
      </div>
      <div className="score-gauge-ends">
        <span>Dovish (-1)</span>
        <span>{clamped.toFixed(3)}</span>
        <span>Hawkish (+1)</span>
      </div>
    </div>
  );
}
