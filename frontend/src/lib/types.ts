// Mirrors backend Pydantic models. Keep field names in sync.

export type ClaimType =
  | "reagent"
  | "equipment"
  | "sample_prep"
  | "procedure"
  | "analysis"
  | "parameter"
  | "dataset"
  | "software";

export type Specificity =
  | "fully_described"
  | "partially_described"
  | "shortcut_citation"
  | "standard_unspecified";

export type ResolutionStatus =
  | "unresolved"
  | "resolving"
  | "resolved"
  | "inferred"
  | "terminal_gap";

export type GapReason =
  | "depth_exceeded"
  | "paywall_or_dead"
  | "source_unavailable"
  | "reference_unresolved"
  | "no_match_in_cited"
  | "no_reference"
  | "parsing_failed";

export interface ChainStep {
  depth: number;
  source_paper_id: string;
  sentence_ids: number[];
  extracted_text: string;
}

export interface Claim {
  claim_id: string;
  paper_id: string;
  type: ClaimType;
  raw_text: string;
  raw_sentence_id: number;
  specificity: Specificity;
  cited_ref_ids: string[];
  resolution_status: ResolutionStatus;
  resolved_text: string | null;
  resolution_chain: ChainStep[];
  terminal_gap_reason: GapReason | null;
  confidence: number;
}

export interface SectionScore {
  section: string;
  score: number;
  n_claims: number;
  n_resolved: number;
}

export interface Gap {
  claim_id: string;
  raw_text: string;
  reason: string;
  chain_trace: Record<string, unknown>[];
  suggested_action: string;
}

export interface ReconstructedProtocol {
  protocol_id: string;
  job_id: string;
  source_paper_id: string;
  title: string;
  methods_evidence_score: number;
  reproducibility_score: number;
  score_methodology: string;
  section_scores: SectionScore[];
  sections: Record<string, Claim[]>;
  gaps: Gap[];
  generated_at: string;
  generation_metadata: Record<string, string | number>;
  version: string;
}

export interface AgentEvent {
  type: string;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface ReconstructionJob {
  job_id: string;
  status:
    | "pending"
    | "ingesting"
    | "decomposing"
    | "resolving"
    | "assembling"
    | "complete"
    | "failed";
  protocol_id: string | null;
  error: string | null;
  timings_ms: Record<string, number>;
}
