"use client";

interface SummaryPanelProps {
  evidenceCount: number;
  primaryFiles: string[];
  relevantSymbols: string[];
  confidence: string;
  status: string;
  verificationStatus: string;
  repairReady: boolean;
}

export default function SummaryPanel({
  evidenceCount,
  primaryFiles,
  relevantSymbols,
  confidence,
  status,
  verificationStatus,
  repairReady,
}: SummaryPanelProps) {
  return (
    <div className="flex items-center gap-4 text-sm">
      <span className="text-fg-muted">Evidence: <span className="text-fg font-medium">{evidenceCount}</span></span>
      <span className="text-fg-muted">Files: <span className="text-fg font-medium">{primaryFiles.length}</span></span>
      <span className="text-fg-muted">Symbols: <span className="text-fg font-medium">{relevantSymbols.length}</span></span>
      <span className="text-fg-muted">Confidence: <span className="text-fg font-medium">{confidence || "—"}</span></span>
      <span className="text-fg-muted">Verification: <span className="text-fg font-medium">{verificationStatus || "—"}</span></span>
      <span className="text-fg-muted">Repair: <span className="text-fg font-medium">{repairReady ? "Ready" : "Not Ready"}</span></span>
    </div>
  );
}
