import type { Gap } from "@/lib/types";
import { cn } from "@/lib/utils";

const REASON_LABEL: Record<string, string> = {
  depth_exceeded: "Citation chain too deep (>5)",
  paywall_or_dead: "Cited paper unavailable",
  source_unavailable: "Full methods text unavailable",
  reference_unresolved: "Bibliography entry could not be resolved",
  no_match_in_cited: "No matching procedure in cited paper",
  no_reference: "No explicit citation",
  parsing_failed: "Could not parse the cited paper",
};

export function GapReport({ gaps }: { gaps: Gap[] }) {
  if (gaps.length === 0) {
    return (
      <div className="rounded-lg border border-accent/30 bg-accentSoft/40 p-6 text-sm">
        No terminal gaps were found. Review any corpus-inferred claims separately.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        These claims could not be reconstructed from publicly accessible
        sources. The agent has logged exactly why, and what to try next.
      </p>
      {gaps.map((g, i) => (
        <div
          key={g.claim_id || i}
          className={cn(
            "rounded-lg border border-warn/30 bg-warnSoft/60 p-4 space-y-2 text-sm",
          )}
        >
          <div className="flex items-start justify-between gap-4">
            <div className="font-medium">
              {REASON_LABEL[g.reason] ?? g.reason}
            </div>
            <span className="font-mono text-[10px] text-muted">{g.reason}</span>
          </div>
          <div className="text-ink/80">{g.raw_text}</div>
          {g.suggested_action && (
            <div className="text-muted text-xs">
              <span className="uppercase tracking-wider font-medium mr-1">
                Suggested:
              </span>
              {g.suggested_action}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
