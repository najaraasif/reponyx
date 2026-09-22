"use client";

interface Step {
  label: string;
  status: "completed" | "current" | "pending" | "failed";
  detail?: string;
}

export default function WorkflowTimeline({ steps }: { steps: Step[] }) {
  return (
    <div className="flex items-center gap-0 overflow-x-auto py-2">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center shrink-0">
          <div className="flex items-center gap-1.5">
            <div
              className={`w-5 h-5 rounded flex items-center justify-center text-[10px] font-medium ${
                step.status === "completed"
                  ? "bg-success/10 text-success"
                  : step.status === "current"
                    ? "bg-accent/10 text-accent"
                    : step.status === "failed"
                      ? "bg-danger/10 text-danger"
                      : "bg-bg-inset text-fg-subtle"
              }`}
            >
              {step.status === "completed" ? "✓" : step.status === "failed" ? "✗" : i + 1}
            </div>
            <span className="text-xs text-fg-muted whitespace-nowrap">{step.label}</span>
          </div>
          {i < steps.length - 1 && (
            <div className={`w-6 h-px mx-1.5 ${step.status === "completed" ? "bg-success/30" : "bg-border"}`} />
          )}
        </div>
      ))}
    </div>
  );
}
