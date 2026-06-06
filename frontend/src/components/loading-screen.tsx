"use client";

import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { FileSearch, GitBranch, Sparkles } from "lucide-react";

const MESSAGES = [
  "Indexing methods",
  "Tracing citations",
  "Resolving gaps",
  "Assembling protocol",
];

const STEPS = ["Ingest", "Trace", "Resolve"];

export function LoadingScreen() {
  const [visible, setVisible] = useState(true);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const messageTimer = window.setInterval(() => {
      setMessageIndex((idx) => (idx + 1) % MESSAGES.length);
    }, 420);
    const exitTimer = window.setTimeout(() => {
      setVisible(false);
    }, 1600);

    return () => {
      window.clearInterval(messageTimer);
      window.clearTimeout(exitTimer);
    };
  }, []);

  if (!visible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#f5f5f7] px-5">
      <div className="w-full max-w-3xl">
        <div className="grid overflow-hidden rounded-[28px] border border-black/[0.07] bg-white shadow-[0_28px_110px_rgba(29,29,31,0.16)] md:grid-cols-[0.95fr_1.05fr]">
          <section className="flex min-h-[360px] flex-col justify-between bg-[#fbfbfd] p-7 md:p-9">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full bg-ink px-3 py-1.5 text-xs font-semibold text-white">
                <Sparkles className="h-3.5 w-3.5" />
                MR
              </div>
              <p className="mt-7 text-sm font-semibold uppercase tracking-[0.24em] text-steel">
                Methods Reconstructor
              </p>
              <h1 className="mt-3 min-h-[72px] text-3xl font-semibold tracking-[-0.03em] text-ink md:text-4xl">
                {MESSAGES[messageIndex]}
              </h1>
            </div>

            <div className="space-y-4">
              <div className="h-1 overflow-hidden rounded-full bg-black/10">
                <div className="h-full w-full origin-left animate-[loader-fill_1.55s_cubic-bezier(0.22,1,0.36,1)_forwards] bg-accent" />
              </div>
              <div className="grid grid-cols-3 gap-2">
                {STEPS.map((step, idx) => (
                  <div key={step} className="rounded-lg border border-black/[0.06] bg-white px-3 py-2">
                    <div className="mb-2 h-1 overflow-hidden rounded-full bg-black/10">
                      <div
                        className="h-full origin-left animate-[loader-fill_1.2s_ease-out_forwards] bg-ink"
                        style={{ animationDelay: `${idx * 180}ms` }}
                      />
                    </div>
                    <p className="text-xs font-semibold text-steel">{step}</p>
                  </div>
                ))}
              </div>
            </div>
          </section>

          <section className="relative min-h-[360px] p-7 md:p-9">
            <div className="absolute left-10 top-12 h-[250px] w-px bg-black/10" />
            <LoadingNode
              icon={<FileSearch className="h-5 w-5" />}
              title="Methods section"
              detail="shortcut citations detected"
            />
            <LoadingNode
              icon={<GitBranch className="h-5 w-5" />}
              title="Citation chain"
              detail="source papers queued"
              className="ml-12 mt-6"
            />
            <div className="ml-4 mt-8 rounded-2xl border border-black/[0.06] bg-[#f5f5f7] p-4">
              <div className="mb-4 flex items-center justify-between">
                <div className="h-3 w-28 rounded-full bg-black/15" />
                <div className="h-6 w-16 rounded-full bg-accentSoft" />
              </div>
              <div className="space-y-3">
                <ProtocolLine width="w-full" />
                <ProtocolLine width="w-11/12" />
                <ProtocolLine width="w-8/12" />
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

function LoadingNode({
  icon,
  title,
  detail,
  className,
}: {
  icon: ReactNode;
  title: string;
  detail: string;
  className?: string;
}) {
  return (
    <div className={`relative flex items-center gap-3 ${className ?? ""}`}>
      <div className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-ink text-white shadow-[0_12px_30px_rgba(29,29,31,0.16)]">
        {icon}
      </div>
      <div className="rounded-2xl border border-black/[0.06] bg-white px-4 py-3 shadow-sm">
        <p className="text-sm font-semibold text-ink">{title}</p>
        <p className="mt-1 text-xs text-steel">{detail}</p>
      </div>
    </div>
  );
}

function ProtocolLine({ width }: { width: string }) {
  return (
    <div className="flex items-center gap-3">
      <div className="h-2.5 w-2.5 rounded-full bg-accent" />
      <div className={`h-3 ${width} rounded-full bg-black/15`} />
    </div>
  );
}
