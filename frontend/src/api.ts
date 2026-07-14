export interface LexiconResult {
  score: number;
  label: string;
  hawkish_hits: Record<string, number>;
  dovish_hits: Record<string, number>;
  word_count: number;
}

export interface SentenceResult {
  sentence: string;
  label: string;
  score: number;
}

export interface ModelResult {
  model_name: string;
  score: number;
  label: string;
  hawkish_count: number;
  dovish_count: number;
  neutral_count: number;
  sentences: SentenceResult[];
}

export interface AnalyzeResponse {
  combined_score: number;
  combined_label: string;
  lexicon: LexiconResult;
  model: ModelResult | null;
}

export interface HealthResponse {
  status: string;
  model_name: string;
  model_loaded: boolean;
  model_load_error: string | null;
}

export interface HistoryPoint {
  doc_id: string | null;
  date: string | null;
  combined_score: number | null;
  combined_score_rolling: number | null;
  combined_label: string | null;
  chair: string | null;
}

export interface FedRegime {
  chair: string;
  start: string;
  end: string | null;
}

export interface HistoryAnnotation {
  type: string;
  start: string | null;
  end: string | null;
  label: string;
}

export interface HighlightMeeting {
  doc_id: string | null;
  date: string;
  combined_score: number;
  combined_score_rolling: number | null;
  combined_label: string;
  chair: string | null;
}

export interface StreakHighlight {
  length: number;
  start_date: string;
  end_date: string;
  chair: string | null;
  end_chair: string | null;
}

export interface ReversalHighlight {
  delta: number;
  before: HighlightMeeting;
  after: HighlightMeeting;
}

export interface ChairStance {
  chair: string | null;
  average_score: number;
  meeting_count: number;
}

export interface HistoryHighlights {
  current: HighlightMeeting;
  trailing_year_average: number | null;
  hawkish_streak: StreakHighlight | null;
  dovish_streak: StreakHighlight | null;
  most_hawkish: HighlightMeeting | null;
  most_dovish: HighlightMeeting | null;
  sharpest_reversal: ReversalHighlight | null;
  by_chair: ChairStance[];
}

export interface HistoryResponse {
  points: HistoryPoint[];
  regimes: FedRegime[];
  annotations: HistoryAnnotation[];
  highlights: HistoryHighlights;
  window: number;
  generated_at: string;
}

export interface PhraseMatch {
  phrase: string;
  category: string;
  start: number;
  end: number;
  weight: number;
}

export interface DocumentDetailResponse {
  doc_id: string;
  date: string | null;
  chair: string | null;
  combined_score: number;
  combined_label: string;
  lexicon_score: number;
  word_count: number;
  text: string;
  matches: PhraseMatch[];
}

export interface FedFundsPoint {
  date: string;
  rate: number;
}

export interface FedFundsResponse {
  points: FedFundsPoint[];
  series_id: string;
  source: string;
  generated_at: string;
}

async function parseErrorBody(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ? JSON.stringify(body.detail) : JSON.stringify(body);
  } catch {
    return res.statusText;
  }
}

export async function analyzeText(text: string, useModel: boolean): Promise<AnalyzeResponse> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, use_model: useModel }),
  });
  if (!res.ok) {
    throw new Error(`Analyze request failed (${res.status}): ${await parseErrorBody(res)}`);
  }
  return res.json();
}

export async function getHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) {
    throw new Error(`Health check failed (${res.status})`);
  }
  return res.json();
}

export async function getHistory(): Promise<HistoryResponse> {
  const res = await fetch("/api/history");
  if (!res.ok) {
    throw new Error(`History request failed (${res.status}): ${await parseErrorBody(res)}`);
  }
  return res.json();
}

export async function getDocument(docId: string): Promise<DocumentDetailResponse> {
  const res = await fetch(`/api/documents/${encodeURIComponent(docId)}`);
  if (!res.ok) {
    throw new Error(`Document request failed (${res.status}): ${await parseErrorBody(res)}`);
  }
  return res.json();
}

export async function getFedFunds(): Promise<FedFundsResponse> {
  const res = await fetch("/api/fedfunds");
  if (!res.ok) {
    throw new Error(`Fed funds request failed (${res.status}): ${await parseErrorBody(res)}`);
  }
  return res.json();
}
