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

export interface HistoryResponse {
  points: HistoryPoint[];
  regimes: FedRegime[];
  annotations: HistoryAnnotation[];
  window: number;
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
