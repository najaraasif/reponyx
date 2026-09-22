"use client";

export default function EvidenceChain({ confidence }: { confidence: string }) {
  const steps = ["Issue", "Implementation", "Test", "Finding", "Conclusion"];
  return (
    <div>
      <div className="section-title">Evidence Chain</div>
      <div className="flex items-center gap-0 text-xs text-fg-muted overflow-x-auto py-1">
        {steps.map((step, i) => (
          <div key={step} className="flex items-center shrink-0">
            <span className="px-2 py-1 bg-bg-inset rounded">{step}</span>
            {i < steps.length - 1 && <span className="mx-1 text-border">→</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
