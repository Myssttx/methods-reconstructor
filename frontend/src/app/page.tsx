import { PaperInput } from "@/components/paper-input";

const EXAMPLES = [
  { label: "Demo: scRNA-seq with citation chain", id: "fixture:paper_a" },
  { label: "Demo: stand-alone methods (Chen 2020)", id: "fixture:chen_2020" },
  { label: "arXiv: 2301.00234 (real fetch)", id: "arxiv:2301.00234" },
];

export default function Home() {
  return (
    <div className="space-y-12">
      <section className="space-y-4 max-w-3xl">
        <p className="text-xs uppercase tracking-widest text-muted">
          Google Cloud Rapid Agent Hackathon · Elastic Track
        </p>
        <h1 className="font-serif text-4xl md:text-5xl leading-tight tracking-tight">
          Turn shortcut-citation-riddled methods sections into self-contained
          reproducible protocols.
        </h1>
        <p className="text-lg text-muted">
          Paste a paper. The agent recursively chases every &ldquo;as described
          in Smith et al.&rdquo;, locates the actual procedure via{" "}
          <span className="text-ink">Elastic hybrid search</span>, and tells you
          exactly where the chain breaks.
        </p>
      </section>

      <section className="rounded-2xl border border-border bg-white p-6 shadow-sm">
        <PaperInput examples={EXAMPLES} />
      </section>

      <section className="grid md:grid-cols-3 gap-6 text-sm">
        <ValueProp
          title="Recursive chain resolver"
          body="When a cited paper itself shortcuts to another paper, the agent recurses — up to a depth cap of 5. Every resolution carries provenance back to the source sentence."
        />
        <ValueProp
          title="Elastic-essential"
          body="Hybrid BM25 + dense vectors locate the specific sentences in a cited paper that match a claim. Pure RAG can't do this — vectors miss paraphrase, BM25 misses synonyms."
        />
        <ValueProp
          title="Gap report, not silence"
          body="Anything we can't resolve is surfaced with a reason and a suggested next action. No hallucinated procedures — we say I don't know, with provenance."
        />
      </section>
    </div>
  );
}

function ValueProp({ title, body }: { title: string; body: string }) {
  return (
    <div className="space-y-2">
      <h3 className="font-medium">{title}</h3>
      <p className="text-muted leading-relaxed">{body}</p>
    </div>
  );
}
