"use client";

import { ArrowRight, LoaderCircle } from "lucide-react";
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
        className="grid gap-3 sm:grid-cols-[1fr_auto]"
      >
        <input
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Paste paper ID, DOI, URL, or fixture"
          className="min-w-0 rounded-full border border-black/[0.10] bg-white px-5 py-3 text-base text-ink shadow-sm outline-none placeholder:text-muted focus:border-accent focus:ring-4 focus:ring-accent/10"
          disabled={busy}
        />
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className={cn(
            "inline-flex items-center justify-center gap-2 rounded-full bg-accent px-6 py-3 text-sm font-semibold text-white shadow-sm",
            "hover:bg-[#0077ed] disabled:cursor-not-allowed disabled:opacity-50",
          )}
        >
          {busy ? (
            <>
              <LoaderCircle className="h-4 w-4 animate-spin" />
              Starting
            </>
          ) : (
            <>
              Reconstruct
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </button>
      </form>

      <div className="flex flex-wrap justify-center gap-2 text-xs text-steel sm:justify-start">
        <span className="mr-1 self-center text-steel">Try</span>
        {examples.map((ex) => (
          <button
            key={ex.id}
            onClick={() => start(ex.id)}
            disabled={busy}
            className="rounded-full bg-[#f5f5f7] px-3 py-1 text-ink ring-1 ring-black/[0.08] hover:text-accent disabled:opacity-50"
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
