"use client";

const confidenceStyles: Record<string, string> = {
  high: "text-success",
  medium: "text-warning",
  low: "text-danger",
};

const verificationStyles: Record<string, string> = {
  supported: "text-success",
  refuted: "text-danger",
  inconclusive: "text-fg-muted",
};

export function ConfidenceBadge({ confidence }: { confidence: string }) {
  const cls = confidenceStyles[confidence] || "text-fg-muted";
  return <span className={`text-xs font-medium ${cls}`}>{confidence}</span>;
}

export function VerificationBadge({ status }: { status: string }) {
  const cls = verificationStyles[status] || "text-fg-muted";
  return <span className={`text-xs font-medium ${cls}`}>{status}</span>;
}

export function EvidenceTypeBadge({ type }: { type: string }) {
  return <span className="text-xs text-fg-muted">{type.replace(/_/g, " ")}</span>;
}

export function EvidenceCategoryBadge({ category }: { category: string }) {
  const labels: Record<string, string> = {
    primary_implementation: "Primary",
    primary_test: "Test",
    supporting: "Supporting",
    unrelated: "Unrelated",
  };
  return <span className="text-xs text-fg-muted">{labels[category] || category}</span>;
}
