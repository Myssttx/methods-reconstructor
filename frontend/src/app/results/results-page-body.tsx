"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { ResultsClient } from "@/components/results-client";

export function ResultsPageBody() {
  const searchParams = useSearchParams();
  const jobId = searchParams.get("job");

  if (!jobId) {
    return (
      <div className="mx-auto max-w-3xl px-5 py-24 text-center">
        <h1 className="text-4xl font-semibold tracking-[-0.035em]">No result selected</h1>
        <p className="mt-4 text-lg text-muted">
          Start a reconstruction from the tool page or add a job ID to the URL.
        </p>
        <Link
          href="/tool"
          className="mt-8 inline-flex rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white"
        >
          Open the tool
        </Link>
      </div>
    );
  }

  return <ResultsClient jobId={jobId} />;
}
