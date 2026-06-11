import type { ReconstructedProtocol } from "@/lib/types";

export function SourceList({ protocol }: { protocol: ReconstructedProtocol }) {
  const sources = new Map<string, Set<number>>();
  sources.set(protocol.source_paper_id, new Set());

  for (const claims of Object.values(protocol.sections)) {
    for (const claim of claims) {
      for (const step of claim.resolution_chain) {
        const sentenceIds = sources.get(step.source_paper_id) ?? new Set<number>();
        step.sentence_ids.forEach((id) => sentenceIds.add(id));
        sources.set(step.source_paper_id, sentenceIds);
      }
    }
  }
  for (const gap of protocol.gaps) {
    for (const item of gap.chain_trace) {
      const source = typeof item.source_paper_id === "string" ? item.source_paper_id : "";
      const ids = Array.isArray(item.sentence_ids)
        ? item.sentence_ids.filter((value): value is number => typeof value === "number")
        : [];
      if (!source) continue;
      const sentenceIds = sources.get(source) ?? new Set<number>();
      ids.forEach((id) => sentenceIds.add(id));
      sources.set(source, sentenceIds);
    }
  }

  return (
    <div className="space-y-3">
      <p className="text-sm leading-6 text-muted">
        Sources used in the reconstructed protocol. Sentence numbers refer to
        the indexed methods text.
      </p>
      {[...sources.entries()].map(([source, sentenceIds], index) => (
        <div key={source} className="rounded-2xl border border-border bg-white p-5">
          <div className="flex gap-4">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-ink text-xs font-semibold text-white">
              {index + 1}
            </span>
            <div>
              <div className="font-mono text-sm text-ink">{source}</div>
              <div className="mt-1 text-xs text-muted">
                {index === 0
                  ? "Original paper"
                  : sentenceIds.size > 0
                    ? `Methods sentences ${[...sentenceIds].sort((a, b) => a - b).join(", ")}`
                    : "Corpus source"}
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
