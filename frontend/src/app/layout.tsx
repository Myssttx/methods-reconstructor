
import type { Metadata } from "next";
import { LoadingScreen } from "@/components/loading-screen";
import "./globals.css";

export const metadata: Metadata = {
  title: "Methods Reconstructor",
  description:
    "Resolve shortcut citations in scientific methods sections. Get a self-contained, reproducible protocol — and a precise list of what could not be recovered.",
  icons: {
    icon: "/favicon.svg",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-paper text-ink antialiased">
        <header className="sticky top-0 z-30 border-b border-black/[0.08] bg-[#fbfbfd]/80 backdrop-blur-xl">
          <div className="mx-auto flex h-11 max-w-6xl items-center justify-between px-5">
            <a href="/" className="flex items-center gap-2 text-[12px] font-semibold">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-ink text-[9px] text-white">
                MR
              </span>
              <span className="hidden sm:inline">Methods Reconstructor</span>
            </a>
            <nav className="flex items-center gap-5 text-[12px] text-steel">
              <a href="/#process" className="hover:text-ink">
                Process
              </a>
              <a href="/#proof" className="hover:text-ink">
                Proof
              </a>
              <a href="/#try" className="hover:text-ink">
                Try
              </a>
              <a
                href="https://github.com/Myssttx/methods-reconstructor"
                className="hidden hover:text-ink sm:inline"
                target="_blank"
                rel="noreferrer"
              >
                GitHub
              </a>
            </nav>
          </div>
        </header>
	<LoadingScreen />
        <main>{children}</main>
        <footer className="border-t border-black/[0.08] bg-[#f5f5f7]">
          <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-6 text-xs text-steel md:flex-row md:items-center md:justify-between">
            <span>Methods Reconstructor</span>
            Recursive citation resolution with source-level provenance. Apache 2.0.
          </div>
        </footer>
      </body>
    </html>
  );
}
