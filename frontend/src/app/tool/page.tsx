import { Database, FileSearch, GitBranch } from "lucide-react";

import { PaperInput } from "@/components/paper-input";

const EXAMPLES = [
  { label: "Fast demo", id: "fixture:paper_a" },
  { label: "Complete methods", id: "fixture:chen_2020" },
  { label: "Jackson breast cancer paper", id: "10.1038/s41586-019-1876-x" },
];

export default function ToolPage() {
  return (
    <div className="bg-[#fbfbfd]">
      <section className="border-b border-black/[0.06] px-5 py-16 text-center md:py-24">
        <p className="text-sm font-semibold text-accent">The core tool</p>
        <h1 className="mx-auto mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.045em] md:text-7xl">
          Reconstruct a paper&apos;s methods.
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-8 text-steel">
          Paste a DOI, PMC ID, arXiv ID, or paper URL. The run can take several
          minutes because it retrieves cited papers and checks their methods.
        </p>
        <div className="mx-auto mt-10 max-w-3xl rounded-[30px] bg-white p-5 shadow-[0_20px_80px_rgba(0,0,0,0.10)] ring-1 ring-black/[0.06] md:p-7">
          <PaperInput examples={EXAMPLES} />
        </div>
      </section>

      <section className="mx-auto grid max-w-6xl gap-4 px-5 py-16 md:grid-cols-3">
        <ToolFact
          icon={FileSearch}
          title="Readable results"
          body="Browse every reconstructed section, source sentence, score, and unresolved gap in the website."
        />
        <ToolFact
          icon={GitBranch}
          title="Citation chains"
          body="The resolver follows shortcut citations recursively instead of treating the first search result as proof."
        />
        <ToolFact
          icon={Database}
          title="Elastic-centered"
          body="Paper caching, hybrid retrieval, claim storage, and provenance stay centered on Elasticsearch."
        />
      </section>
    </div>
  );
}

function ToolFact({
  icon: Icon,
  title,
  body,
}: {
  icon: typeof FileSearch;
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
