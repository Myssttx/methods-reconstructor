"use client";

import { useEffect, useState } from "react";

import { AgentStream } from "@/components/agent-stream";
import { GapReport } from "@/components/gap-report";
import { ProtocolView } from "@/components/protocol-view";
import { ScoreBreakdown } from "@/components/score-breakdown";
import { exportUrl, fetchProtocol } from "@/lib/api";
import type { AgentEvent, ReconstructedProtocol } from "@/lib/types";
import { cn, fmtPct, scoreBg, scoreColor } from "@/lib/utils";

export default function ReconstructionPage({ params }: { params: { jobId: string } }) {
  const { jobId } = params;
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [protocol, setProtocol] = useState<ReconstructedProtocol | null>(null);
  const [status, setStatus] = useState<"running" | "done" | "error">("running");
  const [tab, setTab] = useState<"protocol" | "gaps" | "scores">("protocol");

  function handleEvent(ev: AgentEvent) {
    setEvents((prev) => [...prev, ev]);
    if (ev.type === "complete") {
      setStatus("done");
      fetchProtocol(jobId)
        .then((p) => setProtocol(p as ReconstructedProtocol))
        .catch(() => setStatus("error"));
    }
    if (ev.type === "error") setStatus("error");
  }

  return (
    <div className="space-y-8">
      <header className="space-y-1">
        <p className="text-xs uppercase tracking-widest text-muted">Job {jobId.slice(0, 8)}</p>
        <h1 className="font-serif text-3xl tracking-tight">
          {protocol?.title || "Reconstructing…"}
        </h1>
      </header>

      <div className="grid md:grid-cols-[1fr_360px] gap-8">
        <div className="space-y-6">
          {protocol ? (
            <>
              <div
                className={cn(
                  "rounded-2xl border border-border p-6 flex items-center gap-6",
                  scoreBg(protocol.reproducibility_score),
                )}
              >
                <div className="text-center">
                  <div
                    className={cn(
                      "font-serif text-5xl font-medium",
                      scoreColor(protocol.reproducibility_score),
                    )}
                  >
                    {fmtPct(protocol.reproducibility_score)}
                  </div>
                  <div className="text-xs text-muted uppercase tracking-wider mt-1">
                    Reproducibility
                  </div>
                </div>
                <div className="text-sm text-muted flex-1">
                  <p>
                    Reconstructed from {protocol.source_paper_id}. Built by
                    chasing shortcut citations through Elastic hybrid retrieval
                    until each claim either resolves to source-paper detail or
                    surfaces as a terminal gap.
                  </p>
                </div>
              </div>

              <div className="border-b border-border flex gap-6 text-sm">
                {(["protocol", "gaps", "scores"] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={cn(
                      "py-2 -mb-px border-b-2",
                      tab === t
                        ? "border-ink text-ink font-medium"
                        : "border-transparent text-muted hover:text-ink",
                    )}
                  >
                    {t === "protocol" && "Protocol"}
                    {t === "gaps" && `Gap report (${protocol.gaps.length})`}
                    {t === "scores" && "Score breakdown"}
                  </button>
                ))}
                <div className="ml-auto flex gap-2 py-2">
                  <ExportLink href={exportUrl(jobId, "md")} label="MD" />
                  <ExportLink href={exportUrl(jobId, "json")} label="JSON" />
                  <ExportLink href={exportUrl(jobId, "csv")} label="CSV" />
                </div>
              </div>

              {tab === "protocol" && <ProtocolView protocol={protocol} />}
              {tab === "gaps" && <GapReport gaps={protocol.gaps} />}
              {tab === "scores" && <ScoreBreakdown scores={protocol.section_scores} />}
            </>
          ) : (
            <SkeletonProtocol status={status} />
          )}
        </div>

        <aside className="space-y-3">
          <h2 className="text-sm font-medium text-muted uppercase tracking-wider">
            Agent stream
          </h2>
          <AgentStream jobId={jobId} onEvent={handleEvent} events={events} />
        </aside>
      </div>
    </div>
  );
}

function SkeletonProtocol({ status }: { status: "running" | "done" | "error" }) {
  if (status === "error") {
    return (
      <div className="rounded-lg border border-danger/30 bg-dangerSoft p-6 text-danger">
        Something went wrong. Check the backend logs for the job.
      </div>
    );
  }
  return (
    <div className="space-y-4">
      <div className="h-24 rounded-2xl bg-white border border-border animate-pulse" />
      <div className="h-32 rounded-2xl bg-white border border-border animate-pulse" />
      <div className="h-48 rounded-2xl bg-white border border-border animate-pulse" />
    </div>
  );
}

function ExportLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="text-xs rounded-full border border-border px-2.5 py-1 hover:border-accent hover:text-accent"
    >
      {label}
    </a>
  );
}
