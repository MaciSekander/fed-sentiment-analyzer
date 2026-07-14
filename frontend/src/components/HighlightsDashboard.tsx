import type { HistoryHighlights } from "../api";

interface Props {
  highlights: HistoryHighlights;
}

function formatDate(date: string): string {
  return new Date(`${date}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function StatTile({ label, value, sub, valueClassName }: { label: string; value: string; sub?: string; valueClassName?: string }) {
  return (
    <div className="stat-tile">
      <div className="stat-tile-label">{label}</div>
      <div className={`stat-tile-value ${valueClassName ?? ""}`}>{value}</div>
      {sub && <div className="stat-tile-sub muted">{sub}</div>}
    </div>
  );
}

export default function HighlightsDashboard({ highlights: h }: Props) {
  const current = h.current;
  const yearDelta =
    h.trailing_year_average !== null ? current.combined_score - h.trailing_year_average : null;

  return (
    <div className="highlights-dashboard">
      <div className="stat-tile stat-tile-hero">
        <div className="stat-tile-label">Current stance</div>
        <div className={`stat-tile-value stat-tile-hero-value label-${current.combined_label}`}>
          {current.combined_label.toUpperCase()}
        </div>
        <div className="stat-tile-sub muted">
          {formatDate(current.date)} &middot; {current.chair} &middot; rolling score{" "}
          {(current.combined_score_rolling ?? current.combined_score).toFixed(3)}
        </div>
      </div>

      <div className="stat-tile-row">
        {yearDelta !== null && (
          <StatTile
            label="Vs. trailing 1-year average"
            value={`${yearDelta >= 0 ? "+" : ""}${yearDelta.toFixed(3)}`}
            sub={`1yr avg ${h.trailing_year_average!.toFixed(3)}`}
            valueClassName={yearDelta > 0 ? "label-hawkish" : yearDelta < 0 ? "label-dovish" : "label-neutral"}
          />
        )}
        {h.hawkish_streak && (
          <StatTile
            label="Longest hawkish streak"
            value={`${h.hawkish_streak.length} meetings`}
            sub={`${formatDate(h.hawkish_streak.start_date)} – ${formatDate(h.hawkish_streak.end_date)}`}
            valueClassName="label-hawkish"
          />
        )}
        {h.dovish_streak && (
          <StatTile
            label="Longest dovish streak"
            value={`${h.dovish_streak.length} meetings`}
            sub={`${formatDate(h.dovish_streak.start_date)} – ${formatDate(h.dovish_streak.end_date)}`}
            valueClassName="label-dovish"
          />
        )}
        {h.most_hawkish && (
          <StatTile
            label="Most hawkish period on record"
            value={h.most_hawkish.combined_score.toFixed(3)}
            sub={`${formatDate(h.most_hawkish.date)} · ${h.most_hawkish.chair}`}
            valueClassName="label-hawkish"
          />
        )}
        {h.most_dovish && (
          <StatTile
            label="Most dovish period on record"
            value={h.most_dovish.combined_score.toFixed(3)}
            sub={`${formatDate(h.most_dovish.date)} · ${h.most_dovish.chair}`}
            valueClassName="label-dovish"
          />
        )}
        {h.sharpest_reversal && (
          <StatTile
            label="Sharpest single-meeting reversal"
            value={`Δ ${h.sharpest_reversal.delta.toFixed(3)}`}
            sub={`${formatDate(h.sharpest_reversal.before.date)} → ${formatDate(h.sharpest_reversal.after.date)}`}
          />
        )}
      </div>
    </div>
  );
}
