import type { SectionScore } from "@/lib/types";
import { cn, scoreBg, scoreColor } from "@/lib/utils";

export function ScoreBreakdown({ scores }: { scores: SectionScore[] }) {
  if (scores.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-white p-6 text-sm text-muted">
        No claims were extracted. Score breakdown is unavailable.
      </div>
    );
  }
  return (
    <div className="space-y-3">
      <p className="text-sm text-muted">
        Per-section reproducibility. Procedure and sample-prep are weighted
        highest because that&apos;s where most replication failures originate.
      </p>
      {scores.map((s) => (
        <div key={s.section} className="rounded-lg border border-border bg-white p-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="font-medium capitalize">{s.section.replace(/_/g, " ")}</div>
              <div className="text-xs text-muted">
                {s.n_resolved} / {s.n_claims} resolved
              </div>
            </div>
            <div className={cn("text-2xl font-serif", scoreColor(s.score))}>
              {Math.round(s.score)}
            </div>
          </div>
          <div className="mt-3 h-2 rounded-full bg-border overflow-hidden">
            <div
              className={cn("h-full", scoreBg(s.score))}
              style={{ width: `${Math.max(2, s.score)}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}
