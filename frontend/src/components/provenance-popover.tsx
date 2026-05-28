"use client";

import { ChainTrace } from "./chain-trace";
import type { ChainStep } from "@/lib/types";

export function ProvenancePopover({ chain }: { chain: ChainStep[] }) {
  if (chain.length === 0) {
    return <span className="text-muted">No chain recorded.</span>;
  }
  return <ChainTrace chain={chain} />;
}
