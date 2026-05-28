"use client";

import { useEffect, useState } from "react";

import { fetchJob, fetchProtocol } from "@/lib/api";
import { subscribeAgentStream } from "@/lib/sse";
import type { AgentEvent, ReconstructedProtocol } from "@/lib/types";

export interface ReconstructionState {
  events: AgentEvent[];
  protocol: ReconstructedProtocol | null;
  status: "running" | "done" | "error";
  error: string | null;
}

export function useReconstruction(jobId: string): ReconstructionState {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [protocol, setProtocol] = useState<ReconstructedProtocol | null>(null);
  const [status, setStatus] = useState<"running" | "done" | "error">("running");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const handle = subscribeAgentStream(
      jobId,
      (ev) => {
        setEvents((prev) => [...prev, ev]);
        if (ev.type === "complete") {
          setStatus("done");
          fetchProtocol(jobId)
            .then((p) => setProtocol(p as ReconstructedProtocol))
            .catch((e) => {
              setStatus("error");
              setError(e instanceof Error ? e.message : String(e));
            });
        }
        if (ev.type === "error") {
          setStatus("error");
          setError(String(ev.data?.message ?? "Agent failed"));
        }
      },
      (err) => {
        setError(err instanceof Error ? err.message : String(err));
      },
    );
    return () => handle.close();
  }, [jobId]);

  return { events, protocol, status, error };
}
