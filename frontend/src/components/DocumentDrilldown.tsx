import { useEffect, useState } from "react";
import { getDocument, type DocumentDetailResponse } from "../api";

interface Props {
  docId: string;
  onClose: () => void;
}

function renderHighlightedText(text: string, matches: DocumentDetailResponse["matches"]) {
  if (!matches.length) return text;
  const sorted = [...matches].sort((a, b) => a.start - b.start);
  const pieces: React.ReactNode[] = [];
  let cursor = 0;
  sorted.forEach((m, i) => {
    if (m.start > cursor) pieces.push(text.slice(cursor, m.start));
    pieces.push(
      <mark key={i} className={`highlight-${m.category}`} title={`"${m.phrase}" (${m.category})`}>
        {text.slice(m.start, m.end)}
      </mark>,
    );
    cursor = m.end;
  });
  if (cursor < text.length) pieces.push(text.slice(cursor));
  return pieces;
}

export default function DocumentDrilldown({ docId, onClose }: Props) {
  const [detail, setDetail] = useState<DocumentDetailResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    setDetail(null);
    setError(null);
    setExpanded(false);
    getDocument(docId)
      .then(setDetail)
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [docId]);

  const COLLAPSED_CHARS = 2000;

  return (
    <div className="drilldown">
      <div className="drilldown-header">
        <div>
          {detail && (
            <>
              <span className={`label-${detail.combined_label}`}>{detail.combined_label.toUpperCase()}</span>
              <span className="muted"> &middot; {detail.date} &middot; {detail.chair}</span>
            </>
          )}
        </div>
        <button className="drilldown-close" onClick={onClose} aria-label="Close document">
          &times;
        </button>
      </div>

      {error && <p className="error">Couldn't load this document: {error}</p>}
      {!detail && !error && <p className="muted">Loading document&hellip;</p>}

      {detail && (
        <>
          <p className="muted">
            score {detail.combined_score.toFixed(3)} &middot; {detail.word_count} words &middot;{" "}
            {detail.matches.length} matched phrase{detail.matches.length === 1 ? "" : "s"}
          </p>
          <div className="drilldown-text">
            {renderHighlightedText(
              expanded || detail.text.length <= COLLAPSED_CHARS ? detail.text : detail.text.slice(0, COLLAPSED_CHARS),
              detail.matches.filter((m) => expanded || m.start < COLLAPSED_CHARS),
            )}
            {!expanded && detail.text.length > COLLAPSED_CHARS && "…"}
          </div>
          {detail.text.length > COLLAPSED_CHARS && (
            <button className="example-btn" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Show less" : "Read full document"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
