"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { startReconstruction } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Example {
  label: string;
  id: string;
}

export function PaperInput({ examples }: { examples: Example[] }) {
  const router = useRouter();
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function start(identifier: string) {
    if (!identifier.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const { job_id } = await startReconstruction(identifier.trim());
      router.push(`/reconstruct/${job_id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <div className="space-y-4">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          start(value);
        }}
        className="flex gap-3"
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="arxiv:2301.12345  ·  doi:10.1234/abcd  ·  PMC9876543  ·  or fixture:paper_a"
          className="flex-1 rounded-lg border border-border bg-white px-4 py-3 text-base shadow-sm outline-none focus:border-accent focus:ring-2 focus:ring-accentSoft"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className={cn(
            "rounded-lg bg-ink px-5 py-3 text-sm font-medium text-paper shadow-sm",
            "hover:bg-accent disabled:opacity-50 disabled:cursor-not-allowed",
          )}
        >
          {busy ? "Starting…" : "Reconstruct"}
        </button>
      </form>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="text-muted self-center mr-1">Try:</span>
        {examples.map((ex) => (
          <button
            key={ex.id}
            onClick={() => start(ex.id)}
            disabled={busy}
            className="rounded-full border border-border bg-paper px-3 py-1 hover:border-accent hover:text-accent disabled:opacity-50"
          >
            {ex.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-md bg-dangerSoft border border-danger/30 px-4 py-2 text-sm text-danger">
          {error}
        </div>
      )}
    </div>
  );
}
