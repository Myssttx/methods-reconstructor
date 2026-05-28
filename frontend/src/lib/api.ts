const BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

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
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ identifier }),
    }),
  );
}

export async function fetchProtocol(jobId: string) {
  return jsonOrThrow(fetch(`${BASE}/api/reconstructions/${jobId}/protocol`));
}

export async function fetchJob(jobId: string) {
  return jsonOrThrow(fetch(`${BASE}/api/reconstructions/${jobId}`));
}

export async function fetchFixtures(): Promise<{ fixtures: string[] }> {
  return jsonOrThrow(fetch(`${BASE}/api/papers/_/fixtures`));
}

export function exportUrl(jobId: string, fmt: "json" | "md" | "csv"): string {
  return `${BASE}/api/reconstructions/${jobId}/export.${fmt}`;
}
