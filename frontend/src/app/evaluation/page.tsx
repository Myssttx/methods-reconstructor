import { BarChart3, FlaskConical, ShieldCheck } from "lucide-react";

export default function EvaluationPage() {
  return (
    <div className="mx-auto max-w-6xl px-5 py-16 md:py-24">
      <p className="text-sm font-semibold text-accent">Model evaluation</p>
      <h1 className="mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.045em] md:text-7xl">
        Measure variability before training.
      </h1>
      <p className="mt-6 max-w-3xl text-xl leading-8 text-steel">
        A faster model is not useful if claim boundaries and labels move on
        every run. The repository includes repeat-run metrics and a verified
        JSONL exporter so tuning decisions can be based on evidence.
      </p>

      <div className="mt-12 grid gap-4 md:grid-cols-3">
        <EvalCard
          icon={BarChart3}
          title="Agreement"
          body="Track claim-count spread, signature Jaccard, and classification agreement across repeated runs."
        />
        <EvalCard
          icon={ShieldCheck}
          title="Verified examples"
          body="Export only source-backed claims and citation-chain evidence for training or prompt regression sets."
        />
        <EvalCard
          icon={FlaskConical}
          title="Controlled generation"
          body="Extraction runs at temperature zero with explicit prompt and model versions recorded in reports."
        />
      </div>

      <div className="mt-12 rounded-[28px] bg-[#101318] p-7 text-white md:p-9">
        <h2 className="text-2xl font-semibold">Current honest limitation</h2>
        <p className="mt-3 max-w-3xl leading-7 text-white/65">
          Gemini produced different claim counts on repeated Jackson-paper
          runs. The evaluation workflow makes that instability visible; it does
          not pretend the system is deterministic before the data supports it.
        </p>
      </div>
      <div className="mt-4 rounded-[28px] bg-white p-7 ring-1 ring-black/[0.06] md:p-9">
        <h2 className="text-2xl font-semibold">Cancer stress suite</h2>
        <p className="mt-3 max-w-3xl leading-7 text-steel">
          Five public, methodologically complex cancer papers exercise spatial
          transcriptomics, single-cell sequencing, imaging mass cytometry, and
          multiplexed ion beam imaging. Reports include stage timing, failures,
          gap rate, and evidence coverage.
        </p>
      </div>
    </div>
  );
}

function EvalCard({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof BarChart3;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-[28px] bg-white p-6 ring-1 ring-black/[0.06]">
      <Icon className="h-6 w-6 text-accent" />
      <h2 className="mt-8 text-2xl font-semibold tracking-[-0.025em]">{title}</h2>
      <p className="mt-3 leading-7 text-steel">{body}</p>
    </div>
  );
}
