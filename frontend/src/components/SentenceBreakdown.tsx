import type { SentenceResult } from "../api";

export default function SentenceBreakdown({ sentences }: { sentences: SentenceResult[] }) {
  if (sentences.length === 0) return null;

  return (
    <ul className="sentence-list">
      {sentences.map((s, i) => (
        <li key={i} className={`sentence-item label-${s.label}`}>
          <span className="sentence-tag">{s.label}</span>
          <span className="sentence-text">{s.sentence}</span>
          <span className="sentence-score">{s.score.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}
