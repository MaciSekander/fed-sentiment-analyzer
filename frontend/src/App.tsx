import { useEffect, useState } from "react";
import { analyzeText, getHealth, type AnalyzeResponse, type HealthResponse } from "./api";
import ScoreGauge from "./components/ScoreGauge";
import SentenceBreakdown from "./components/SentenceBreakdown";
import LexiconHits from "./components/LexiconHits";
import HistoryView from "./components/HistoryView";

const EXAMPLES: Record<string, string> = {
  Hawkish:
    "The Committee decided to raise the target range for the federal funds rate, citing persistently high inflation and upside risks that call for a restrictive stance of monetary policy.",
  Dovish:
    "The Committee decided to lower the target range and remain highly accommodative to support economic activity given downside risks to growth.",
  Neutral: "The meeting was held in the offices of the Board of Governors in Washington, D.C.",
};

type Tab = "analyze" | "history";

export default function App() {
  const [tab, setTab] = useState<Tab>("analyze");

  const [text, setText] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  async function handleAnalyze() {
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await analyzeText(text, true);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <p className="eyebrow">Macro research tool</p>
        <h1>Fed Sentiment Analyzer</h1>
        <p className="subtitle">
          Paste FOMC minutes, a statement, or a speech excerpt to classify it as hawkish, dovish, or neutral, or
          browse how Fed communication has shifted across every chair's tenure since 1967.
        </p>
        {health && !health.model_loaded && (
          <p className="warning">
            Transformer model unavailable ({health.model_load_error ?? "unknown error"}) &mdash; falling back to the
            lexicon baseline only.
          </p>
        )}

        <div className="tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === "analyze"}
            className={`tab-btn ${tab === "analyze" ? "active" : ""}`}
            onClick={() => setTab("analyze")}
          >
            Analyze
          </button>
          <button
            role="tab"
            aria-selected={tab === "history"}
            className={`tab-btn ${tab === "history" ? "active" : ""}`}
            onClick={() => setTab("history")}
          >
            History
          </button>
        </div>
      </header>

      {tab === "analyze" && (
        <>
          <section className="input-section">
            <div className="examples">
              <span>Try an example:</span>
              {Object.entries(EXAMPLES).map(([name, sample]) => (
                <button key={name} className="example-btn" onClick={() => setText(sample)}>
                  {name}
                </button>
              ))}
            </div>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="Paste text here..."
              rows={8}
            />
            <button className="analyze-btn" onClick={handleAnalyze} disabled={loading || !text.trim()}>
              {loading ? "Analyzing..." : "Analyze"}
            </button>
          </section>

          {error && <p className="error">{error}</p>}

          {result && (
            <section className="results">
              <ScoreGauge score={result.combined_score} label={result.combined_label} />

              <div className="results-grid">
                <div className="card">
                  <h3>Lexicon baseline</h3>
                  <p className="score-line">
                    score <strong>{result.lexicon.score.toFixed(3)}</strong> ({result.lexicon.label}) &middot;{" "}
                    {result.lexicon.word_count} words
                  </p>
                  <LexiconHits hawkishHits={result.lexicon.hawkish_hits} dovishHits={result.lexicon.dovish_hits} />
                </div>

                <div className="card">
                  <h3>Transformer model</h3>
                  {result.model ? (
                    <>
                      <p className="score-line">
                        score <strong>{result.model.score.toFixed(3)}</strong> ({result.model.label}) &middot;{" "}
                        {result.model.model_name}
                      </p>
                      <p className="muted">
                        {result.model.hawkish_count} hawkish / {result.model.dovish_count} dovish /{" "}
                        {result.model.neutral_count} neutral sentence(s)
                      </p>
                      <SentenceBreakdown sentences={result.model.sentences} />
                    </>
                  ) : (
                    <p className="muted">Model unavailable for this request; combined score is lexicon-only.</p>
                  )}
                </div>
              </div>
            </section>
          )}
        </>
      )}

      {tab === "history" && <HistoryView />}
    </div>
  );
}
