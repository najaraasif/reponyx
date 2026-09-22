"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { HealthResponse } from "@/lib/types";

interface Metric {
  label: string;
  value: string;
  description: string;
}

export default function EvaluationsPage() {
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    api.health().then(setHealth).catch(() => {});
  }, []);

  const retrievalMetrics: Metric[] = [
    { label: "Recall@5", value: "—", description: "Relevant items retrieved in top 5" },
    { label: "Precision@5", value: "—", description: "Relevant items among retrieved" },
    { label: "MRR", value: "—", description: "Mean reciprocal rank of first relevant result" },
  ];

  const repairMetrics: Metric[] = [
    { label: "Success Rate", value: "—", description: "Repairs that pass all tests" },
    { label: "Evidence Rate", value: "—", description: "Repairs with supporting evidence" },
    { label: "Test Pass Rate", value: "—", description: "Tests passing after repair" },
  ];

  return (
    <div className="page">
      <Header title="Evaluations" subtitle="Engineering metrics and benchmarks" />

      <section className="mb-5">
        <div className="section-title">System</div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-fg-muted">Version</span>
          <span className="text-fg">{health?.version || "—"}</span>
          <span className="text-fg-muted">Environment</span>
          <span className="text-fg">{health?.environment || "—"}</span>
        </div>
      </section>

      <div className="grid grid-cols-2 gap-5">
        <section>
          <div className="section-title">Retrieval Metrics</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {retrievalMetrics.map((m) => (
                  <tr key={m.label}>
                    <td className="text-sm font-medium text-fg">{m.label}</td>
                    <td className="font-mono text-sm text-fg">{m.value}</td>
                    <td className="text-xs text-fg-muted">{m.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section>
          <div className="section-title">Repair Metrics</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Metric</th>
                  <th>Value</th>
                  <th>Description</th>
                </tr>
              </thead>
              <tbody>
                {repairMetrics.map((m) => (
                  <tr key={m.label}>
                    <td className="text-sm font-medium text-fg">{m.label}</td>
                    <td className="font-mono text-sm text-fg">{m.value}</td>
                    <td className="text-xs text-fg-muted">{m.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}
