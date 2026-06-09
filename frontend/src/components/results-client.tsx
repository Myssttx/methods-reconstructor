"use client";

import type { ReactNode } from "react";
import { useCallback, useEffect, useState } from "react";
import {
  CheckCircle2,
  Download,
  FileSearch,
  GitBranch,
  LoaderCircle,
} from "lucide-react";

import { AgentStream } from "@/components/agent-stream";
import { GapReport } from "@/components/gap-report";
import { ProtocolView } from "@/components/protocol-view";
import { ScoreBreakdown } from "@/components/score-breakdown";
import { SourceList } from "@/components/source-list";
import { exportUrl, fetchJob, fetchProtocol } from "@/lib/api";
import type { AgentEvent, ReconstructedProtocol } from "@/lib/types";
import { cn, fmtPct, scoreBg, scoreColor } from "@/lib/utils";

type ResultTab = "protocol" | "gaps" | "scores" | "sources";

export function ResultsClient({ jobId }: { jobId: string }) {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [protocol, setProtocol] = useState<ReconstructedProtocol | null>(null);
  const [status, setStatus] = useState<"running" | "done" | "error">("running");
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<ResultTab>("protocol");

  const loadProtocol = useCallback(() => {
    fetchProtocol(jobId)
      .then((value) => {
        setProtocol(value as ReconstructedProtocol);
        setStatus("done");
      })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : String(reason));
        setStatus("error");
      });
  }, [jobId]);

  useEffect(() => {
    fetchJob(jobId)
      .then((job) => {
        if (job.status === "complete") {
          loadProtocol();
        } else if (job.status === "failed") {
          setError(job.error || "The reconstruction failed.");
          setStatus("error");
        }
      })
      .catch((reason) => {
        setError(reason instanceof Error ? reason.message : String(reason));
        setStatus("error");
      });
  }, [jobId, loadProtocol]);

  const handleEvent = useCallback(
    (event: AgentEvent) => {
      setEvents((previous) => [...previous, event]);
      if (event.type === "complete") {
        loadProtocol();
      }
      if (event.type === "error") {
        setError(String(event.data?.message ?? "The reconstruction failed."));
        setStatus("error");
      }
    },
    [loadProtocol],
  );

  const evidenceScore =
    protocol?.methods_evidence_score ?? protocol?.reproducibility_score ?? 0;

  return (
    <div className="mx-auto max-w-7xl px-5 py-10 md:py-14">
      <header className="mb-8 flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
            Reconstruction {jobId.slice(0, 8)}
          </p>
          <h1 className="mt-2 max-w-4xl text-3xl font-semibold tracking-[-0.035em] md:text-5xl">
            {protocol?.title || "Reconstructing the methods"}
          </h1>
        </div>
        {protocol && (
          <a
            href={exportUrl(jobId, "pdf")}
            className="inline-flex items-center justify-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white hover:bg-accent"
          >
            <Download className="h-4 w-4" />
            Download formatted PDF
          </a>
        )}
      </header>

      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-6">
          {protocol ? (
            <>
              <div
                className={cn(
                  "rounded-[28px] border border-border p-6 md:flex md:items-center md:gap-8",
                  scoreBg(evidenceScore),
                )}
              >
                <div className="text-center">
                  <div className={cn("text-6xl font-semibold", scoreColor(evidenceScore))}>
                    {fmtPct(evidenceScore)}
                  </div>
                  <div className="mt-1 text-xs font-semibold uppercase tracking-wider text-muted">
                    Evidence coverage
                  </div>
                </div>
                <p className="mt-5 flex-1 text-sm leading-6 text-muted md:mt-0">
                  Every visible result can be opened to inspect its original
                  sentence and citation chain. Unresolved details remain in the
                  gap report instead of being silently filled in.
                </p>
              </div>

              <div className="overflow-x-auto border-b border-border">
                <div className="flex min-w-max items-center gap-5 text-sm">
                  {(["protocol", "gaps", "scores", "sources"] as const).map((item) => (
                    <button
                      key={item}
                      onClick={() => setTab(item)}
                      className={cn(
                        "-mb-px border-b-2 py-3 capitalize",
                        tab === item
                          ? "border-ink font-semibold text-ink"
                          : "border-transparent text-muted hover:text-ink",
                      )}
                    >
                      {item === "gaps" ? `Gaps (${protocol.gaps.length})` : item}
                    </button>
                  ))}
                  <div className="ml-auto flex gap-2 py-2">
                    <ExportLink href={exportUrl(jobId, "json")} label="JSON" />
                    <ExportLink href={exportUrl(jobId, "csv")} label="Gap CSV" />
                  </div>
                </div>
              </div>

              {tab === "protocol" && <ProtocolView protocol={protocol} />}
              {tab === "gaps" && <GapReport gaps={protocol.gaps} />}
              {tab === "scores" && <ScoreBreakdown scores={protocol.section_scores} />}
              {tab === "sources" && <SourceList protocol={protocol} />}
            </>
          ) : (
            <SkeletonProtocol status={status} error={error} />
          )}
        </div>

        <aside className="space-y-3">
          <h2 className="text-xs font-semibold uppercase tracking-[0.2em] text-muted">
            Live agent activity
          </h2>
          <AgentStream jobId={jobId} onEvent={handleEvent} events={events} />
        </aside>
      </div>
    </div>
  );
}

function SkeletonProtocol({
  status,
  error,
}: {
  status: "running" | "done" | "error";
  error: string | null;
}) {
  if (status === "error") {
    return (
      <div className="rounded-2xl border border-danger/30 bg-dangerSoft p-6 text-danger">
        <div className="font-semibold">The reconstruction could not finish.</div>
        <div className="mt-2 text-sm">{error || "Check the backend logs for this job."}</div>
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-[28px] border border-border bg-white shadow-sm">
      <div className="border-b border-border bg-[#fbfbfd] p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-muted">
              Reconstruction in progress
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.03em]">
              Chasing methods through the citation chain
            </h2>
          </div>
          <div className="inline-flex items-center gap-2 rounded-full bg-accentSoft px-3 py-2 text-sm font-semibold text-accent">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            Vertex AI working
          </div>
        </div>
        <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-black/10">
          <div className="h-full w-full origin-left animate-[loader-fill_2.4s_cubic-bezier(0.22,1,0.36,1)_infinite] bg-accent" />
        </div>
      </div>
      <div className="grid gap-0 md:grid-cols-3">
        <LoadingStep icon={<FileSearch className="h-4 w-4" />} label="Parse methods" />
        <LoadingStep icon={<GitBranch className="h-4 w-4" />} label="Resolve citations" />
        <LoadingStep icon={<CheckCircle2 className="h-4 w-4" />} label="Assemble protocol" />
      </div>
    </div>
  );
}

function LoadingStep({ icon, label }: { icon: ReactNode; label: string }) {
  return (
    <div className="border-b border-border p-5 last:border-b-0 md:border-b-0 md:border-r md:last:border-r-0">
      <div className="grid h-9 w-9 place-items-center rounded-xl bg-ink text-white">{icon}</div>
      <div className="mt-4 text-sm font-semibold">{label}</div>
      <div className="mt-1 text-xs text-muted">Running source-level checks</div>
    </div>
  );
}

function ExportLink({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      className="rounded-full border border-border px-3 py-1.5 text-xs hover:border-accent hover:text-accent"
    >
      {label}
    </a>
  );
}
