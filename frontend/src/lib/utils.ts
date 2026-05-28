import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function fmtPct(n: number | null | undefined): string {
  if (n == null) return "—";
  return `${Math.round(n)}%`;
}

export function scoreColor(score: number): string {
  if (score >= 80) return "text-accent";
  if (score >= 50) return "text-warn";
  return "text-danger";
}

export function scoreBg(score: number): string {
  if (score >= 80) return "bg-accentSoft";
  if (score >= 50) return "bg-warnSoft";
  return "bg-dangerSoft";
}
