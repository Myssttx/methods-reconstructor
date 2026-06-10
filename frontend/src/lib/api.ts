import type { ReconstructionJob } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

// Always include the API key header if one is configured.
function authHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return API_KEY ? { "X-API-Key": API_KEY, ...extra } : extra;
}

async function jsonOrThrow<T>(p: Promise<Response>): Promise<T> {
  const resp = await p;
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`API ${resp.status}: ${text || resp.statusText}`);
  }
  return resp.json() as Promise<T>;
}

export async function startReconstruction(identifier: string): Promise<{
  job_id: string;
  stream_url: string;
}> {
  return jsonOrThrow(
    fetch(`${BASE}/api/reconstructions`, {
      method: "POST",
      headers: authHeaders({ "content-type": "application/json" }),
      body: JSON.stringify({ identifier }),
    }),
  );
}

export async function fetchProtocol(jobId: string) {
  return jsonOrThrow(fetch(`${BASE}/api/reconstructions/${jobId}/protocol`, { headers: authHeaders() }));
}

export async function fetchJob(jobId: string): Promise<ReconstructionJob> {
  return jsonOrThrow(fetch(`${BASE}/api/reconstructions/${jobId}`, { headers: authHeaders() }));
}

export async function fetchFixtures(): Promise<{ fixtures: string[] }> {
  return jsonOrThrow(fetch(`${BASE}/api/papers/_/fixtures`, { headers: authHeaders() }));
}

export function exportUrl(jobId: string, fmt: "json" | "md" | "csv"): string {
  // Export is a direct browser navigation — append key as query param for simplicity.
  const url = `${BASE}/api/reconstructions/${jobId}/export.${fmt}`;
  return API_KEY ? `${url}?api_key=${API_KEY}` : url;
}
