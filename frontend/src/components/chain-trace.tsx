import type { ChainStep } from "@/lib/types";

export function ChainTrace({ chain }: { chain: ChainStep[] }) {
  return (
    <div>
      <div className="font-medium text-muted uppercase tracking-wider mb-1">
        Resolution chain
      </div>
      <ol className="space-y-2">
        {chain.map((step, i) => (
          <li key={i} className="border-l-2 border-accent/40 pl-3">
            <div className="text-muted">
              <span className="font-mono">depth {step.depth}</span> · {step.source_paper_id}
              {step.sentence_ids.length > 0 && (
                <span> · sentence {step.sentence_ids.join(", ")}</span>
              )}
            </div>
            {step.extracted_text && (
              <div className="mt-1 text-ink/80">{step.extracted_text.slice(0, 240)}{step.extracted_text.length > 240 ? "…" : ""}</div>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
