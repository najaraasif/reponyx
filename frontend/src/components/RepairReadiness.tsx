"use client";

interface RepairReadinessProps {
  hasEvidence: boolean;
  hasRootCause: boolean;
  hasAffectedFiles: boolean;
  confidence: string;
  affectedFiles: string[];
  onCreateRepair: () => void;
  creatingRepair: boolean;
}

export default function RepairReadiness({
  hasEvidence,
  hasRootCause,
  hasAffectedFiles,
  affectedFiles,
  onCreateRepair,
  creatingRepair,
}: RepairReadinessProps) {
  const ready = hasEvidence && hasRootCause && hasAffectedFiles;

  return (
    <div>
      <div className="section-title">Repair Readiness</div>
      <div className="border border-border rounded p-3">
        <div className="space-y-1.5 mb-3">
          <CheckItem checked={hasEvidence} label="Evidence collected" />
          <CheckItem checked={hasRootCause} label="Root cause identified" />
          <CheckItem checked={hasAffectedFiles} label={`Affected files (${affectedFiles.length})`} />
        </div>
        {ready ? (
          <button onClick={onCreateRepair} disabled={creatingRepair} className="btn-primary">
            {creatingRepair ? "Creating..." : "Create Repair"}
          </button>
        ) : (
          <p className="text-xs text-fg-subtle">Insufficient evidence for automated repair.</p>
        )}
      </div>
    </div>
  );
}

function CheckItem({ checked, label }: { checked: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${checked ? "bg-success border-success text-white" : "border-border"}`}>
        {checked && (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>
      <span className={checked ? "text-fg" : "text-fg-muted"}>{label}</span>
    </div>
  );
}
