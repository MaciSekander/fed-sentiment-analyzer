import type { HistoryHighlights } from "../api";

function formatMonthYear(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  });
}

// Deterministic string templating off the already-computed highlights --
// no AI generation, no new endpoint. Deliberately doesn't reference the
// all-time longest streak here (that's a distinct "longest ever" stat, not
// necessarily the streak still in progress -- misattributing it as "the
// current run" would be misleading); the streak tiles below carry that
// context on their own terms instead.
export function buildLede(h: HistoryHighlights): string {
  const current = h.current;
  const score = (current.combined_score_rolling ?? current.combined_score).toFixed(2);

  let comparison = "in line with the past year's average";
  if (h.trailing_year_average !== null) {
    const delta = current.combined_score - h.trailing_year_average;
    if (delta > 0.05) comparison = "more hawkish than the past year's average";
    else if (delta < -0.05) comparison = "more dovish than the past year's average";
  }

  return (
    `As of ${formatMonthYear(current.date)}, Fed communication reads ${current.combined_label}, ` +
    `with a rolling score of ${score} — ${comparison}, under ${current.chair}.`
  );
}
