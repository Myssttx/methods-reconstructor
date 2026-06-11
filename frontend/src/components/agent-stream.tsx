"use client";

import { useEffect, useRef } from "react";

import { subscribeAgentStream } from "@/lib/sse";
import type { AgentEvent } from "@/lib/types";
import { cn } from "@/lib/utils";

interface Props {
  jobId: string;
  events: AgentEvent[];
  onEvent: (ev: AgentEvent) => void;
}

export function AgentStream({ jobId, events, onEvent }: Props) {
  const onEventRef = useRef(onEvent);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  useEffect(() => {
    const handle = subscribeAgentStream(jobId, (event) => onEventRef.current(event));
    return () => handle.close();
  }, [jobId]);

  return (
    <div className="space-y-1 max-h-[70vh] overflow-y-auto rounded-lg border border-border bg-white p-2 text-xs">
      {events.length === 0 && (
        <div className="text-muted px-2 py-1">Waiting for first event…</div>
      )}
      {events.map((ev, i) => (
        <EventRow key={i} ev={ev} />
      ))}
    </div>
  );
}

function EventRow({ ev }: { ev: AgentEvent }) {
  const tone = EVENT_TONE[ev.type] ?? "default";
  return (
    <div
      className={cn(
        "rounded-md px-2 py-1.5 flex items-start gap-2",
        tone === "good" && "bg-accentSoft/50",
        tone === "warn" && "bg-warnSoft/40",
        tone === "bad" && "bg-dangerSoft/50",
      )}
    >
      <span className="font-mono text-[10px] text-muted shrink-0 pt-0.5">
        {ev.timestamp.slice(11, 19)}
      </span>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-[11px] font-semibold">
          {labelFor(ev.type)}
        </div>
        <div className="text-muted truncate">{describe(ev)}</div>
      </div>
    </div>
  );
}

const EVENT_TONE: Record<string, "good" | "warn" | "bad" | "default"> = {
  ingest: "good",
  decompose: "good",
  complete: "good",
  assemble: "good",
  performance: "good",
  "chain.fetching": "default",
  "chain.fetch_failed": "warn",
  error: "bad",
};

function labelFor(type: string): string {
  switch (type) {
    case "ingest":
      return "INGESTED";
    case "decompose":
      return "DECOMPOSED";
    case "status":
      return "STATUS";
    case "claim_resolved":
      return "CLAIM";
    case "chain.fetching":
      return "↘ fetching";
    case "chain.fetch_failed":
      return "✗ fetch failed";
    case "assemble":
      return "ASSEMBLED";
    case "complete":
      return "COMPLETE";
    case "performance":
      return "TIMING";
    case "error":
      return "ERROR";
    default:
      return type.toUpperCase();
  }
}

function describe(ev: AgentEvent): string {
  const d = ev.data || {};
  if (ev.type === "ingest") return `${d.title ?? ""} · ${d.n_references ?? 0} refs`;
  if (ev.type === "decompose") {
    const bySpec = (d.by_specificity || {}) as Record<string, number>;
    const counts = Object.entries(bySpec).map(([k, v]) => `${k}: ${v}`).join("  ");
    const mode = String(d.extraction_mode || "unknown");
    return d.cache_hit ? `cached · ${mode}  ${counts}` : `${mode}  ${counts}`;
  }
  if (ev.type === "status") return String(d.message ?? "");
  if (ev.type === "claim_resolved") {
    const r = d.status === "resolved" ? "✓" : "✗";
    return `${r} ${d.type} · depth ${d.chain_depth} · ${(d.raw_text as string) || ""}`;
  }
  if (ev.type === "chain.fetching") return `ref ${d.ref_id} (depth ${d.depth})`;
  if (ev.type === "chain.fetch_failed") return `ref ${d.ref_id} — unavailable`;
  if (ev.type === "assemble") return `score ${d.score} · ${d.n_gaps} gaps`;
  if (ev.type === "performance") {
    const timings = (d.timings_ms || {}) as Record<string, number>;
    return Object.entries(timings)
      .map(([name, milliseconds]) => `${name}: ${(milliseconds / 1000).toFixed(1)}s`)
      .join("  ");
  }
  if (ev.type === "complete") return "Protocol ready";
  if (ev.type === "error") return String(d.message ?? "");
  return JSON.stringify(d).slice(0, 80);
}
