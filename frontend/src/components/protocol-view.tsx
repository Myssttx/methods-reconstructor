import { ClaimCard } from "./claim-card";
import type { ReconstructedProtocol } from "@/lib/types";

const SECTION_ORDER = [
  "reagent",
  "reagents",
  "equipment",
  "sample_prep",
  "procedure",
  "analysis",
  "parameter",
  "software",
  "dataset",
  "datasets",
];

const SECTION_TITLES: Record<string, string> = {
  reagent: "Reagents & Materials",
  reagents: "Reagents & Materials",
  equipment: "Equipment",
  sample_prep: "Sample Preparation",
  procedure: "Procedure",
  analysis: "Data Analysis",
  parameter: "Parameters",
  software: "Software",
  dataset: "Datasets",
  datasets: "Datasets",
};

export function ProtocolView({ protocol }: { protocol: ReconstructedProtocol }) {
  const orderedSections = SECTION_ORDER.filter((k) => protocol.sections[k]?.length);
  // Append any other section names not in the canonical order.
  const otherSections = Object.keys(protocol.sections).filter(
    (k) => !SECTION_ORDER.includes(k) && protocol.sections[k].length > 0,
  );
  const sections = [...orderedSections, ...otherSections];

  if (sections.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-white p-6 text-muted text-sm">
        No reconstructed sections. Every claim ended up in the gap report — see
        the Gap report tab.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {sections.map((sec) => (
        <section key={sec} className="space-y-3">
          <h2 className="font-serif text-xl tracking-tight">
            {SECTION_TITLES[sec] ?? sec.replace(/_/g, " ")}
          </h2>
          <div className="space-y-3">
            {protocol.sections[sec].map((claim) => (
              <ClaimCard key={claim.claim_id} claim={claim} />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
