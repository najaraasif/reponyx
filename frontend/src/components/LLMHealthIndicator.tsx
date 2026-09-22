"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { LLMHealthResponse } from "@/lib/types";

export default function LLMHealthIndicator() {
  const [health, setHealth] = useState<LLMHealthResponse | null>(null);

  useEffect(() => {
    api.llmHealth().then(setHealth).catch(() => {});
  }, []);

  if (!health) return null;

  return (
    <div className="px-3 py-1.5 text-[11px]">
      <div className="flex items-center justify-between">
        <span className="text-fg-subtle">LLM</span>
        <span className={`w-1.5 h-1.5 rounded-full ${health.available ? "bg-success" : "bg-warning"}`} />
      </div>
      <div className="text-fg-subtle font-mono">{health.provider}/{health.model}</div>
    </div>
  );
}
