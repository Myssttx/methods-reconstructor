import { ArrowRight, CheckCircle2, FileText, Search, TriangleAlert } from "lucide-react";

import { PaperInput } from "@/components/paper-input";

const EXAMPLES = [
  { label: "scRNA-seq chain", id: "fixture:paper_a" },
  { label: "complete methods", id: "fixture:chen_2020" },
  { label: "arXiv fetch", id: "arxiv:2301.00234" },
];

export default function Home() {
  return (
    <div className="bg-paper">
      <section className="shine-surface overflow-hidden border-b border-black/[0.06]">
        <div className="mx-auto flex min-h-[calc(100vh-44px)] max-w-6xl flex-col items-center px-5 pb-12 pt-14 text-center md:pt-20">
          <p className="text-sm font-semibold text-accent">Methods Reconstructor</p>
          <h1 className="mt-4 max-w-5xl text-5xl font-semibold leading-[0.96] tracking-[-0.04em] text-ink md:text-7xl lg:text-8xl">
            Rebuild the missing method.
          </h1>
          <p className="mt-6 max-w-2xl text-xl leading-8 tracking-[-0.01em] text-steel md:text-2xl md:leading-9">
            Turn shortcut citations into a clean, reproducible protocol with
            every step traced back to the paper it came from.
          </p>
          <div className="mt-7 flex items-center justify-center gap-6 text-lg">
            <a href="#try" className="inline-flex items-center gap-1 text-accent hover:underline">
              Try it <ArrowRight className="h-4 w-4" />
            </a>
            <a
              href="https://github.com/Myssttx/methods-reconstructor"
              className="inline-flex items-center gap-1 text-accent hover:underline"
              target="_blank"
              rel="noreferrer"
            >
              View code <ArrowRight className="h-4 w-4" />
            </a>
          </div>

          <div className="soft-orbit mt-10 w-full max-w-5xl">
            <ProductMockup />
          </div>
        </div>
      </section>

      <section id="process" className="px-3 py-3">
        <div className="grid gap-3 md:grid-cols-2">
          <FeaturePanel
            eyebrow="Before"
            title="Methods that point somewhere else."
            body="Papers often replace the actual procedure with a citation. Then that cited paper does it again."
            variant="dark"
          >
            <ShortcutCard />
          </FeaturePanel>
          <FeaturePanel
            eyebrow="After"
            title="A protocol you can inspect."
            body="Resolved steps stay in the protocol. Missing steps are separated into a gap report instead of being guessed."
            variant="light"
          >
            <ProtocolCard />
          </FeaturePanel>
        </div>
      </section>

      <section id="proof" className="bg-white px-5 py-20 text-center md:py-28">
        <div className="mx-auto max-w-5xl">
          <h2 className="text-4xl font-semibold tracking-[-0.035em] md:text-6xl">
            Built for provenance, not vibes.
          </h2>
          <p className="mx-auto mt-5 max-w-3xl text-xl leading-8 text-steel">
            Each claim moves through retrieval, citation-chain resolution, and
            assembly. The output shows what resolved, where it came from, and
            what still needs a human.
          </p>
          <div className="mt-12 grid gap-3 md:grid-cols-3">
            <ProofTile icon={Search} title="Find" body="Locate exact method sentences in cited papers." />
            <ProofTile icon={CheckCircle2} title="Trace" body="Keep the source sentence attached to every claim." />
            <ProofTile icon={TriangleAlert} title="Stop" body="Flag missing details instead of fabricating them." />
          </div>
        </div>
      </section>

      <section id="try" className="px-3 pb-3">
        <div className="mx-auto max-w-none overflow-hidden bg-[#fbfbfd] px-5 py-16 text-center md:py-24">
          <h2 className="text-4xl font-semibold tracking-[-0.035em] md:text-6xl">
            Try a reconstruction.
          </h2>
          <p className="mx-auto mt-4 max-w-2xl text-lg leading-7 text-steel">
            Use a demo fixture for the fastest run, or paste an arXiv ID, DOI,
            PMC ID, URL, or PDF path once the backend is running.
          </p>
          <div className="mx-auto mt-9 max-w-3xl rounded-[28px] bg-white p-4 shadow-[0_18px_70px_rgba(0,0,0,0.10)] ring-1 ring-black/[0.06] md:p-6">
            <PaperInput examples={EXAMPLES} />
          </div>
        </div>
      </section>
    </div>
  );
}

function ProductMockup() {
  return (
    <div className="relative mx-auto rounded-[34px] bg-[#1d1d1f] p-2 shadow-[0_30px_120px_rgba(0,0,0,0.22)] md:rounded-[44px] md:p-3">
      <div className="overflow-hidden rounded-[28px] bg-white md:rounded-[36px]">
        <div className="flex items-center justify-between border-b border-black/[0.06] px-5 py-3 text-xs text-steel">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
            <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
          </div>
          <span>paper_a reconstruction</span>
        </div>
        <div className="grid min-h-[430px] gap-0 md:grid-cols-[0.88fr_1.12fr]">
          <div className="bg-[#f5f5f7] p-5 text-left md:p-8">
            <div className="mb-7 flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center rounded-2xl bg-white shadow-sm">
                <FileText className="h-5 w-5 text-accent" />
              </div>
              <div>
                <div className="text-sm font-semibold">Original methods</div>
                <div className="text-xs text-steel">3 unresolved shortcuts</div>
              </div>
            </div>
            <PaperLine width="w-full" />
            <PaperLine width="w-11/12" />
            <HighlightedLine />
            <PaperLine width="w-10/12" />
            <PaperLine width="w-7/12" />
            <div className="mt-8 rounded-3xl bg-white p-4 shadow-sm ring-1 ring-black/[0.05]">
              <div className="text-xs font-semibold uppercase tracking-[0.14em] text-steel">
                Chain
              </div>
              <div className="mt-4 space-y-3 text-sm">
                <MiniStep label="ref_1" status="shortcut" />
                <MiniStep label="ref_7" status="resolved" />
                <MiniStep label="ref_12" status="gap" />
              </div>
            </div>
          </div>
          <div className="p-5 text-left md:p-8">
            <div className="mb-5 inline-flex rounded-full bg-accentSoft px-3 py-1 text-sm font-semibold text-accent">
              Reconstructed protocol
            </div>
            <h3 className="max-w-xl text-3xl font-semibold tracking-[-0.03em] md:text-4xl">
              The cited procedure, pulled back into view.
            </h3>
            <div className="mt-8 space-y-4">
              <ProtocolStep n="1" text="Wash cells twice in PBS." />
              <ProtocolStep n="2" text="Lyse for 10 minutes on ice." />
              <ProtocolStep n="3" text="Centrifuge at 12,000g, then retain the supernatant." />
            </div>
            <div className="mt-8 rounded-3xl bg-[#f5f5f7] p-5">
              <div className="text-sm font-semibold">Gap report</div>
              <p className="mt-2 text-sm leading-6 text-steel">
                One parameter is not recoverable from the citation chain. The
                source paper delegates it to a missing supplement.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function FeaturePanel({
  eyebrow,
  title,
  body,
  variant,
  children,
}: {
  eyebrow: string;
  title: string;
  body: string;
  variant: "dark" | "light";
  children: React.ReactNode;
}) {
  const dark = variant === "dark";
  return (
    <div
      className={
        dark
          ? "overflow-hidden bg-[#1d1d1f] px-6 py-10 text-white md:min-h-[720px] md:px-12 md:py-16"
          : "overflow-hidden bg-white px-6 py-10 text-ink md:min-h-[720px] md:px-12 md:py-16"
      }
    >
      <div className="mx-auto max-w-2xl text-center">
        <p className={dark ? "text-sm font-semibold text-[#a1a1a6]" : "text-sm font-semibold text-accent"}>
          {eyebrow}
        </p>
        <h2 className="mt-3 text-4xl font-semibold tracking-[-0.035em] md:text-6xl">
          {title}
        </h2>
        <p className={dark ? "mt-4 text-lg leading-7 text-[#d2d2d7]" : "mt-4 text-lg leading-7 text-steel"}>
          {body}
        </p>
      </div>
      <div className="mx-auto mt-12 max-w-2xl">{children}</div>
    </div>
  );
}

function ShortcutCard() {
  return (
    <div className="rounded-[34px] bg-[#2c2c2e] p-6 text-left shadow-2xl">
      <p className="text-sm leading-7 text-[#f5f5f7]">
        Cells were prepared using the protocol described previously
        <span className="mx-1 rounded-full bg-[#3a3a3c] px-2 py-1 text-[#ffd60a]">[ref_1]</span>
        with minor modifications.
      </p>
      <div className="mt-8 space-y-3">
        <MiniStep label="ref_1 points to ref_7" status="shortcut" dark />
        <MiniStep label="ref_7 contains the procedure" status="resolved" dark />
        <MiniStep label="supplement link missing" status="gap" dark />
      </div>
    </div>
  );
}

function ProtocolCard() {
  return (
    <div className="rounded-[34px] bg-[#f5f5f7] p-6 text-left shadow-[0_18px_70px_rgba(0,0,0,0.10)]">
      <div className="mb-6 flex items-center justify-between">
        <span className="text-sm font-semibold">Protocol</span>
        <span className="rounded-full bg-accentSoft px-3 py-1 text-xs font-semibold text-accent">
          82% resolved
        </span>
      </div>
      <div className="space-y-4">
        <ProtocolStep n="1" text="Wash cells twice in PBS." />
        <ProtocolStep n="2" text="Lyse for 10 minutes on ice." />
        <ProtocolStep n="3" text="Centrifuge at 12,000g." />
      </div>
    </div>
  );
}

function ProofTile({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof Search;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-[28px] bg-[#f5f5f7] p-6 text-left">
      <Icon className="h-6 w-6 text-accent" />
      <h3 className="mt-8 text-2xl font-semibold tracking-[-0.025em]">{title}</h3>
      <p className="mt-3 leading-7 text-steel">{body}</p>
    </div>
  );
}

function PaperLine({ width }: { width: string }) {
  return <div className={`mb-3 h-3 rounded-full bg-black/[0.09] ${width}`} />;
}

function HighlightedLine() {
  return (
    <div className="mb-3 rounded-full bg-[#fff2c7] px-3 py-2 text-xs font-medium text-[#6d4b00]">
      as described in [ref_1]
    </div>
  );
}

function MiniStep({
  label,
  status,
  dark = false,
}: {
  label: string;
  status: "shortcut" | "resolved" | "gap";
  dark?: boolean;
}) {
  const color =
    status === "resolved" ? "bg-[#34c759]" : status === "gap" ? "bg-[#ff3b30]" : "bg-[#ffcc00]";
  return (
    <div className={dark ? "flex items-center gap-3 text-sm text-[#f5f5f7]" : "flex items-center gap-3 text-sm text-steel"}>
      <span className={`h-2.5 w-2.5 rounded-full ${color}`} />
      <span>{label}</span>
    </div>
  );
}

function ProtocolStep({ n, text }: { n: string; text: string }) {
  return (
    <div className="flex gap-4 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-black/[0.05]">
      <div className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-white">
        {n}
      </div>
      <p className="leading-7 text-steel">{text}</p>
    </div>
  );
}
