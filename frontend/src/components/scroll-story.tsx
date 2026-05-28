"use client";

import { CheckCircle2, FileSearch, GitBranch, Search, TriangleAlert } from "lucide-react";
import { useEffect, useRef, useState } from "react";

const CHAPTERS = [
  {
    kicker: "01 / Ingest",
    title: "The paper becomes a structured map.",
    body: "Methods text, references, and sentence IDs are separated so every downstream step can point back to the source.",
    metric: "24 sentences",
    icon: FileSearch,
  },
  {
    kicker: "02 / Search",
    title: "Shortcut citations are located, not guessed.",
    body: "The agent searches cited papers for the exact passage that explains the borrowed procedure.",
    metric: "BM25 + vectors",
    icon: Search,
  },
  {
    kicker: "03 / Resolve",
    title: "The chain keeps moving until it stops.",
    body: "If a cited paper points to another method, the resolver follows the next link with a hard depth cap.",
    metric: "depth 0-5",
    icon: GitBranch,
  },
  {
    kicker: "04 / Report",
    title: "The final answer separates proof from gaps.",
    body: "Resolved steps become a protocol. Missing details become a gap report with the reason they failed.",
    metric: "82% resolved",
    icon: CheckCircle2,
  },
];

export function ScrollStory() {
  const [active, setActive] = useState(0);
  const refs = useRef<Array<HTMLDivElement | null>>([]);

  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) {
          return;
        }
        const idx = Number((visible.target as HTMLElement).dataset.index);
        if (!Number.isNaN(idx)) {
          setActive(idx);
        }
      },
      { rootMargin: "-30% 0px -30% 0px", threshold: [0.25, 0.5, 0.75] },
    );

    refs.current.forEach((node) => {
      if (node) {
        observer.observe(node);
      }
    });

    return () => observer.disconnect();
  }, []);

  return (
    <section id="process" className="bg-[#05070a] text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-20 md:grid-cols-[0.92fr_1.08fr] md:py-28">
        <div className="md:sticky md:top-24 md:h-[calc(100vh-8rem)]">
          <div className="flex h-full items-center">
            <StoryVisual active={active} />
          </div>
        </div>

        <div className="space-y-10 md:py-[12vh]">
          {CHAPTERS.map((chapter, idx) => (
            <div
              key={chapter.title}
              ref={(node) => {
                refs.current[idx] = node;
              }}
              data-index={idx}
              className={
                active === idx
                  ? "min-h-[54vh] rounded-[36px] bg-white p-8 text-ink shadow-2xl transition-all duration-500 md:p-10"
                  : "min-h-[54vh] rounded-[36px] bg-white/[0.055] p-8 text-white/55 ring-1 ring-white/10 transition-all duration-500 md:p-10"
              }
            >
              <chapter.icon
                className={active === idx ? "h-7 w-7 text-accent" : "h-7 w-7 text-white/35"}
              />
              <p className="mt-12 text-sm font-semibold uppercase tracking-[0.24em]">
                {chapter.kicker}
              </p>
              <h2 className="mt-4 max-w-xl text-4xl font-semibold tracking-[-0.04em] md:text-6xl">
                {chapter.title}
              </h2>
              <p
                className={
                  active === idx
                    ? "mt-5 max-w-xl text-lg leading-8 text-steel"
                    : "mt-5 max-w-xl text-lg leading-8 text-white/50"
                }
              >
                {chapter.body}
              </p>
              <div
                className={
                  active === idx
                    ? "mt-10 inline-flex rounded-full bg-accentSoft px-4 py-2 text-sm font-semibold text-accent"
                    : "mt-10 inline-flex rounded-full bg-white/10 px-4 py-2 text-sm font-semibold text-white/50"
                }
              >
                {chapter.metric}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function StoryVisual({ active }: { active: number }) {
  return (
    <div className="relative w-full overflow-hidden rounded-[42px] bg-[#0d1117] p-3 shadow-[0_35px_120px_rgba(0,0,0,0.45)] ring-1 ring-white/10">
      <div className="rounded-[32px] bg-[#f5f5f7] p-5 text-ink md:p-7">
        <div className="flex items-center justify-between border-b border-black/[0.08] pb-4">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.22em] text-steel">
              Reconstruction
            </div>
            <div className="mt-1 text-sm font-semibold">paper_a</div>
          </div>
          <div className="rounded-full bg-ink px-3 py-1 text-xs font-semibold text-white">
            step {active + 1}/4
          </div>
        </div>

        <div className="mt-6 grid gap-4">
          <AnimatedSentence active={active >= 0} text="Cells were prepared as described in [ref_1]." />
          <AnimatedSentence active={active >= 1} text="Elastic locates the cited method passage." />
          <ChainRail active={active} />
          <ProtocolPreview active={active} />
        </div>
      </div>
    </div>
  );
}

function AnimatedSentence({ active, text }: { active: boolean; text: string }) {
  return (
    <div
      className={
        active
          ? "rounded-3xl bg-white p-4 shadow-sm ring-1 ring-black/[0.06] transition-all duration-500"
          : "translate-y-3 rounded-3xl bg-white/50 p-4 opacity-45 ring-1 ring-black/[0.04] transition-all duration-500"
      }
    >
      <p className="text-sm leading-6 text-steel">{text}</p>
    </div>
  );
}

function ChainRail({ active }: { active: number }) {
  const items = ["source", "ref_1", "ref_7", "gap"];
  return (
    <div className="rounded-3xl bg-[#111827] p-4 text-white">
      <div className="mb-4 flex items-center justify-between text-xs uppercase tracking-[0.2em] text-white/45">
        <span>Citation chain</span>
        <span>{active >= 2 ? "resolved" : "walking"}</span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {items.map((item, idx) => {
          const isActive = idx <= active;
          const isGap = item === "gap";
          return (
            <div key={item} className="space-y-2">
              <div
                className={
                  isActive
                    ? isGap && active >= 3
                      ? "h-2 rounded-full bg-[#ff3b30]"
                      : "h-2 rounded-full bg-accent"
                    : "h-2 rounded-full bg-white/15"
                }
              />
              <div className={isActive ? "text-xs text-white" : "text-xs text-white/35"}>
                {item}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ProtocolPreview({ active }: { active: number }) {
  return (
    <div className="rounded-3xl bg-white p-4 shadow-sm ring-1 ring-black/[0.06]">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm font-semibold">Protocol preview</span>
        {active >= 3 ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-accentSoft px-3 py-1 text-xs font-semibold text-accent">
            <CheckCircle2 className="h-3.5 w-3.5" />
            Ready
          </span>
        ) : (
          <span className="rounded-full bg-[#f5f5f7] px-3 py-1 text-xs font-semibold text-steel">
            Building
          </span>
        )}
      </div>
      <div className="space-y-3">
        <PreviewStep active={active >= 1} text="Wash cells twice in PBS." />
        <PreviewStep active={active >= 2} text="Lyse for 10 minutes on ice." />
        <PreviewGap active={active >= 3} />
      </div>
    </div>
  );
}

function PreviewStep({ active, text }: { active: boolean; text: string }) {
  return (
    <div className={active ? "flex items-center gap-3 text-sm text-steel" : "flex items-center gap-3 text-sm text-black/25"}>
      <span className={active ? "h-2 w-2 rounded-full bg-[#34c759]" : "h-2 w-2 rounded-full bg-black/15"} />
      <span>{text}</span>
    </div>
  );
}

function PreviewGap({ active }: { active: boolean }) {
  return (
    <div className={active ? "flex items-center gap-3 text-sm text-steel" : "flex items-center gap-3 text-sm text-black/25"}>
      <TriangleAlert className={active ? "h-4 w-4 text-[#ff3b30]" : "h-4 w-4 text-black/20"} />
      <span>Missing supplement flagged as a gap.</span>
    </div>
  );
}
