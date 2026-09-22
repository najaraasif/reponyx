"use client";

import { useState } from "react";

interface EvidenceCardProps {
  type: string;
  content: string;
  sourceFile: string;
  lineRange: [number, number];
  relevance: number;
}

export default function EvidenceCard({ type, content, sourceFile, lineRange }: EvidenceCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border border-border rounded cursor-pointer hover:bg-bg-subtle transition-colors" onClick={() => setExpanded(!expanded)}>
      <div className="flex items-center justify-between px-3 py-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs text-fg-muted">{type.replace(/_/g, " ")}</span>
          <span className="font-mono text-xs text-fg-muted">{sourceFile}:{lineRange[0]}-{lineRange[1]}</span>
        </div>
        <svg
          className={`w-3 h-3 text-fg-subtle transition-transform shrink-0 ${expanded ? "rotate-180" : ""}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </div>
      {expanded && (
        <div className="px-3 pb-2 border-t border-border-subtle">
          <pre className="text-xs text-fg-muted font-mono bg-bg-inset rounded p-2 mt-2 overflow-x-auto whitespace-pre-wrap">{content}</pre>
        </div>
      )}
    </div>
  );
}
