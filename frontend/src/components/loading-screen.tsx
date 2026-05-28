"use client";

import { useEffect, useState } from "react";

const MESSAGES = [
  "Indexing methods",
  "Tracing citations",
  "Resolving gaps",
  "Assembling protocol",
];

export function LoadingScreen() {
  const [visible, setVisible] = useState(true);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const messageTimer = window.setInterval(() => {
      setMessageIndex((idx) => (idx + 1) % MESSAGES.length);
    }, 420);
    const exitTimer = window.setTimeout(() => {
      setVisible(false);
    }, 1600);

    return () => {
      window.clearInterval(messageTimer);
      window.clearTimeout(exitTimer);
    };
  }, []);

  if (!visible) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-[#f5f5f7]">
      <div className="w-full max-w-sm px-8 text-center">
        <div className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-ink text-sm font-semibold text-white shadow-[0_20px_60px_rgba(0,0,0,0.18)]">
          MR
        </div>
        <div className="mt-8 overflow-hidden">
          <p className="text-xs font-semibold uppercase tracking-[0.32em] text-steel">
            Methods Reconstructor
          </p>
          <p className="mt-3 h-7 text-lg font-semibold tracking-[-0.02em] text-ink">
            {MESSAGES[messageIndex]}
          </p>
        </div>
        <div className="mt-7 h-px overflow-hidden rounded-full bg-black/10">
          <div className="h-full w-full origin-left animate-[loader-fill_1.55s_cubic-bezier(0.22,1,0.36,1)_forwards] bg-ink" />
        </div>
      </div>
    </div>
  );
}
