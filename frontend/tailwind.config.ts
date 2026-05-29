import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1d1d1f",
        paper: "#f5f5f7",
        accent: "#0071e3",
        accentSoft: "#eaf3ff",
        gold: "#bf8f2c",
        graphite: "#1d1d1f",
        steel: "#515154",
        warn: "#9b6c00",
        warnSoft: "#fcefc8",
        danger: "#b3261e",
        dangerSoft: "#fde0de",
        muted: "#6b7280",
        border: "#e5e1d8",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "-apple-system", "system-ui", "Inter", "Helvetica", "Arial", "sans-serif"],
        serif: ["ui-serif", "Georgia", "Cambria", "Times New Roman", "serif"],
        mono: ["ui-monospace", "Menlo", "Monaco", "Consolas", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
