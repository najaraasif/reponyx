"use client";

import { useEffect, useState } from "react";
import Header from "@/components/Header";
import { api } from "@/lib/api";
import type { LLMHealthResponse } from "@/lib/types";

const providers = [
  { name: "Mock", key: "mock", description: "Deterministic responses for testing" },
  { name: "Ollama", key: "ollama", description: "Local model via Ollama" },
  { name: "OpenAI", key: "openai", description: "GPT models via OpenAI API" },
];

export default function LLMPage() {
  const [health, setHealth] = useState<LLMHealthResponse | null>(null);

  useEffect(() => {
    api.llmHealth().then(setHealth).catch(() => {});
  }, []);

  return (
    <div className="page">
      <Header title="LLM / Providers" subtitle="Language model configuration and status" />

      <section className="mb-5">
        <div className="section-title">Current Provider</div>
        {health ? (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Provider</th>
                  <th>Model</th>
                  <th>Status</th>
                  <th>Available</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="font-mono text-xs">{health.provider}</td>
                  <td className="font-mono text-xs">{health.model}</td>
                  <td>
                    <span className={`badge ${health.status === "ok" ? "badge-success" : "badge-danger"}`}>
                      {health.status}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${health.available ? "badge-success" : "badge-danger"}`}>
                      {health.available ? "yes" : "no"}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        ) : (
          <div className="skeleton h-10 w-full" />
        )}
      </section>

      <section className="mb-5">
        <div className="section-title">Available Providers</div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Key</th>
                <th>Description</th>
                <th>Active</th>
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.key}>
                  <td className="text-sm font-medium text-fg">{p.name}</td>
                  <td className="font-mono text-xs text-fg-muted">{p.key}</td>
                  <td className="text-sm text-fg-muted">{p.description}</td>
                  <td>
                    {health?.provider === p.key && (
                      <span className="badge-success">active</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <div className="section-title">Configuration</div>
        <div className="text-sm text-fg-muted space-y-1">
          <div>Set provider via <code className="font-mono text-xs bg-bg-inset px-1 rounded">REPONYX_LLM_PROVIDER</code> environment variable</div>
          <div>Set API key via <code className="font-mono text-xs bg-bg-inset px-1 rounded">REPONYX_LLM_API_KEY</code> environment variable</div>
          <div>Set model via <code className="font-mono text-xs bg-bg-inset px-1 rounded">REPONYX_LLM_MODEL</code> environment variable</div>
        </div>
      </section>
    </div>
  );
}
