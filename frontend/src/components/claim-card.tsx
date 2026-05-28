"use client";

import { useState } from "react";

import type { Claim } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ChainTrace } from "./chain-trace";

const SPECIFICITY_LABEL: Record<string, string> = {
  fully_described: "fully described in original",
  partially_described: "partially described",
  shortcut_citation: "resolved from cited paper",
  standard_unspecified: "inferred 'standard' from corpus",
};

export function ClaimCard({ claim }: { claim: Claim }) {
  const [open, setOpen] = useState(false);
  const text = claim.resolved_text || claim.raw_text;
  const fromOriginal = claim.specificity === "fully_described";
  const sourceLabel =
    claim.resolution_chain.length > 0
      ? `from ${claim.resolution_chain[claim.resolution_chain.length - 1].source_paper_id}`
      : "original paper";

  return (
    <div className="rounded-lg border border-border bg-white">
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full text-left px-4 py-3 flex items-start gap-3 hover:bg-paper"
      >
        <span
          className={cn(
            "mt-1 inline-block h-2 w-2 rounded-full shrink-0",
            fromOriginal ? "bg-muted" : "bg-accent",
          )}
        />
        <div className="flex-1 space-y-1">
          <p className="text-sm leading-relaxed whitespace-pre-line">{text}</p>
          <div className="text-xs text-muted flex flex-wrap items-center gap-3">
            <span className="uppercase tracking-wider">{claim.type}</span>
            <span>·</span>
            <span>{SPECIFICITY_LABEL[claim.specificity] ?? claim.specificity}</span>
            <span>·</span>
            <span>{sourceLabel}</span>
            {claim.confidence > 0 && (
              <>
                <span>·</span>
                <span>confidence {(claim.confidence * 100).toFixed(0)}%</span>
              </>
            )}
          </div>
        </div>
        <span className="text-xs text-muted shrink-0 pt-1">{open ? "−" : "+"}</span>
      </button>

      {open && (
        <div className="border-t border-border px-4 py-3 space-y-3 text-xs">
          <div>
            <div className="font-medium text-muted uppercase tracking-wider mb-1">
              Original sentence
            </div>
            <div className="text-muted">{claim.raw_text}</div>
          </div>
          {claim.resolution_chain.length > 0 && <ChainTrace chain={claim.resolution_chain} />}
        </div>
      )}
    </div>
  );
}
