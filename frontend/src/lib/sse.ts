import type { AgentEvent } from "./types";

const BASE = process.env.NEXT_PUBLIC_SSE_URL || "http://localhost:8000";
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || "";

export interface SseHandle {
  close(): void;
}

export function subscribeAgentStream(
  jobId: string,
  onEvent: (ev: AgentEvent) => void,
  onError?: (err: unknown) => void,
): SseHandle {
  const queryParam = API_KEY ? `?api_key=${encodeURIComponent(API_KEY)}` : "";
  const url = `${BASE}/api/reconstructions/${jobId}/stream${queryParam}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    try {
      const parsed = JSON.parse(e.data) as AgentEvent;
      onEvent(parsed);
      if (parsed.type === "complete" || parsed.type === "error") {
        es.close();
      }
    } catch (err) {
      onError?.(err);
    }
  };

  es.onerror = (err) => {
    onError?.(err);
  };

  return { close: () => es.close() };
}
