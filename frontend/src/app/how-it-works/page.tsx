import { ScrollStory } from "@/components/scroll-story";

export default function HowItWorksPage() {
  return (
    <div>
      <section className="bg-white px-5 py-20 text-center md:py-28">
        <p className="text-sm font-semibold text-accent">System design</p>
        <h1 className="mx-auto mt-4 max-w-4xl text-5xl font-semibold tracking-[-0.045em] md:text-7xl">
          Retrieval first. Provenance always.
        </h1>
        <p className="mx-auto mt-6 max-w-3xl text-xl leading-8 text-steel">
          Methods Reconstructor separates extraction, retrieval, recursive
          resolution, and final assembly so unsupported details can be rejected
          before they reach the protocol.
        </p>
      </section>
      <ScrollStory />
    </div>
  );
}
