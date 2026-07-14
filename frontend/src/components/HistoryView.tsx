import { useEffect, useMemo, useState } from "react";
import { getFedFunds, getHistory, type FedFundsResponse, type HistoryResponse } from "../api";
import { computeTimeDomain } from "../lib/chartTime";
import { buildLede } from "../lib/narrative";
import Timeline from "./Timeline";
import FedFundsChart from "./FedFundsChart";
import DocumentDrilldown from "./DocumentDrilldown";
import HighlightsDashboard from "./HighlightsDashboard";
import RegimeLegend from "./RegimeLegend";

export default function HistoryView() {
  const [history, setHistory] = useState<HistoryResponse | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [fedFunds, setFedFunds] = useState<FedFundsResponse | null>(null);
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null);

  useEffect(() => {
    getHistory()
      .then(setHistory)
      .catch((err) => setHistoryError(err instanceof Error ? err.message : String(err)));
    getFedFunds()
      .then(setFedFunds)
      .catch(() => setFedFunds(null)); // the rate chart is a nice-to-have, not core -- fail quietly
  }, []);

  const domain = useMemo<[number, number] | null>(() => {
    if (!history) return null;
    return computeTimeDomain(
      history.points.map((p) => p.date),
      history.regimes,
    );
  }, [history]);

  if (historyError) {
    return <p className="error">Couldn't load history: {historyError}</p>;
  }
  if (!history || !domain) {
    return <p className="muted">Loading historical data&hellip;</p>;
  }

  return (
    <section className="history-section">
      <p className="lede prose">{buildLede(history.highlights)}</p>

      <div className="chart-block">
        <h2 className="section-heading">Sentiment over time</h2>
        <Timeline history={history} domain={domain} onSelectDocument={setSelectedDocId} />
        {fedFunds && <FedFundsChart fedFunds={fedFunds} domain={domain} />}
      </div>

      {selectedDocId && (
        <DocumentDrilldown docId={selectedDocId} onClose={() => setSelectedDocId(null)} />
      )}

      <h2 className="section-heading">Key highlights</h2>
      <HighlightsDashboard highlights={history.highlights} />

      <h2 className="section-heading">Fed Chair eras &amp; data notes</h2>
      <RegimeLegend regimes={history.regimes} annotations={history.annotations} byChair={history.highlights.by_chair} />
    </section>
  );
}
