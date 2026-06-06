"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { CheckCircle2, FileSearch, GitBranch, LoaderCircle } from "lucide-react";

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
    <div className="overflow-hidden rounded-2xl border border-border bg-white shadow-sm">
      <div className="border-b border-border bg-[#fbfbfd] p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">
              Reconstruction in progress
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-ink">
              Chasing methods through the citation chain
            </h2>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-accentSoft px-3 py-2 text-sm font-semibold text-accent">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            Gemini working
          </div>
        </div>
        <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-black/10">
          <div className="h-full w-full origin-left animate-[loader-fill_2.4s_cubic-bezier(0.22,1,0.36,1)_infinite] bg-accent" />
        </div>
      </div>

      <div className="grid gap-0 md:grid-cols-[0.9fr_1.1fr]">
        <div className="border-b border-border p-6 md:border-b-0 md:border-r">
          <div className="space-y-4">
            <LoadingStep icon={<FileSearch className="h-4 w-4" />} label="Parse methods section" />
            <LoadingStep icon={<GitBranch className="h-4 w-4" />} label="Resolve shortcut citations" />
            <LoadingStep icon={<CheckCircle2 className="h-4 w-4" />} label="Score recoverability" />
          </div>
        </div>

        <div className="p-6">
          <div className="mb-5 flex items-center justify-between">
            <div>
              <div className="h-3 w-32 rounded-full bg-black/15" />
              <div className="mt-2 h-2.5 w-52 rounded-full bg-black/10" />
            </div>
            <div className="h-10 w-10 rounded-full bg-accentSoft" />
          </div>
          <div className="space-y-3">
            <SkeletonLine width="w-full" />
            <SkeletonLine width="w-11/12" />
            <SkeletonLine width="w-9/12" />
          </div>
          <div className="mt-6 rounded-xl bg-[#f5f5f7] p-4">
            <div className="mb-4 h-3 w-24 rounded-full bg-black/15" />
            <div className="space-y-3">
              <SkeletonLine width="w-10/12" />
              <SkeletonLine width="w-8/12" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function LoadingStep({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-border bg-[#fbfbfd] p-3">
      <div className="grid h-9 w-9 place-items-center rounded-lg bg-ink text-white">{icon}</div>
      <div>
        <p className="text-sm font-semibold text-ink">{label}</p>
        <p className="mt-1 text-xs text-muted">running source-level checks</p>
      </div>
    </div>
  );
}

function SkeletonLine({ width }: { width: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-2.5 w-2.5 rounded-full bg-accent/70" />
      <div className={cn("h-3 animate-pulse rounded-full bg-black/10", width)} />
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
