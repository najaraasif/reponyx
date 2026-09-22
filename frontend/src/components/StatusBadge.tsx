"use client";

const variants: Record<string, string> = {
  completed: "badge-success",
  success: "badge-success",
  approved: "badge-success",
  pending: "badge-warning",
  pending_review: "badge-warning",
  running: "badge-info",
  analyzing: "badge-info",
  failed: "badge-danger",
  error: "badge-danger",
  rejected: "badge-danger",
  cancelled: "badge-neutral",
  created: "badge-info",
  supported: "badge-success",
  inconclusive: "badge-warning",
  refuted: "badge-danger",
};

export default function StatusBadge({ status }: { status: string }) {
  const s = status || "unknown";
  const cls = variants[s] || "badge-neutral";
  return <span className={cls}>{s.replace(/_/g, " ")}</span>;
}
