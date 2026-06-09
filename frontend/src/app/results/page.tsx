import { Suspense } from "react";

import { ResultsPageBody } from "./results-page-body";

export default function ResultsPage() {
  return (
    <Suspense fallback={<div className="mx-auto max-w-7xl px-5 py-16">Loading result...</div>}>
      <ResultsPageBody />
    </Suspense>
  );
}
