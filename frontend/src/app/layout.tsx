import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Methods Reconstructor",
  description:
    "Resolve shortcut citations in scientific methods sections. Get a self-contained, reproducible protocol — and a precise list of what could not be recovered.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-paper text-ink antialiased">
        <header className="border-b border-border">
          <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
            <a href="/" className="font-serif text-xl tracking-tight">
              Methods Reconstructor
            </a>
            <nav className="text-sm text-muted">
              <a
                href="https://github.com/Myssttx/methods-reconstructor"
                className="hover:text-ink"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-10">{children}</main>
        <footer className="mt-20 border-t border-border">
          <div className="mx-auto max-w-6xl px-6 py-6 text-xs text-muted">
            Powered by Elastic hybrid search + a recursive citation-resolving agent. Apache 2.0.
          </div>
        </footer>
      </body>
    </html>
  );
}
