import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#0b0d10",
        paper: "#fbfaf6",
        accent: "#1e6f4e",
        accentSoft: "#d6efe1",
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
