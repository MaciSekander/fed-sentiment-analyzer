// Shared time-axis helpers for the History tab's stacked charts (Timeline +
// FedFundsChart) -- both compute their x-domain from the same source so the
// two panels' axes line up pixel-for-pixel, and both share this syncId so
// hovering one shows a synced crosshair on the other.
export const HISTORY_CHART_SYNC_ID = "fed-history";

export function parseDateToTs(date: string | null): number | null {
  return date ? Date.parse(`${date}T00:00:00Z`) : null;
}

export function computeTimeDomain(
  dataDates: (string | null)[],
  regimes: { start: string; end: string | null }[],
): [number, number] {
  const dataTs = dataDates.map(parseDateToTs).filter((t): t is number => t !== null);
  const regimeTs = regimes.flatMap((r) => {
    const start = parseDateToTs(r.start);
    const end = r.end ? parseDateToTs(r.end) : Date.now();
    return [start, end].filter((t): t is number => t !== null);
  });
  const all = [...dataTs, ...regimeTs];
  return [Math.min(...all), Math.max(...all)];
}
