"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Repository, RepositoryAnalysis } from "@/lib/types";

export default function RepositoryDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [repo, setRepo] = useState<Repository | null>(null);
  const [analysis, setAnalysis] = useState<RepositoryAnalysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [issue, setIssue] = useState("");
  const [creatingInvestigation, setCreatingInvestigation] = useState(false);
  const [creatingRepair, setCreatingRepair] = useState(false);

  useEffect(() => {
    api.repositories.get(id).then(setRepo).catch(() => {});
    api.repositories.structure(id).then((d) => setAnalysis(d as RepositoryAnalysis)).catch(() => {});
  }, [id]);

  async function handleAnalyze() {
    setAnalyzing(true);
    try {
      const result = await api.repositories.analyze(id);
      setAnalysis(result);
      setRepo((r) => r ? { ...r, status: "analyzed" } : r);
    } catch {}
    setAnalyzing(false);
  }

  async function handleCreateInvestigation() {
    if (!issue.trim()) return;
    setCreatingInvestigation(true);
    try {
      const inv = await api.investigations.create(id, issue.trim());
      window.location.href = `/investigations/${inv.investigation_id}`;
    } catch {}
    setCreatingInvestigation(false);
  }

  async function handleCreateRepair() {
    if (!issue.trim()) return;
    setCreatingRepair(true);
    try {
      const repair = await api.repairs.create(id, issue.trim());
      window.location.href = `/repairs/${repair.repair_id}`;
    } catch {}
    setCreatingRepair(false);
  }

  if (!repo) {
    return (
      <div className="page">
        <Header title="Repository" />
        <div className="skeleton h-64 w-full" />
      </div>
    );
  }

  const repoName = repo.url.split("/").slice(-2).join("/");

  return (
    <div className="page">
      <Header
        title={repoName}
        subtitle={
          <span className="flex items-center gap-2">
            <span className="font-mono text-xs text-fg-subtle">{id}</span>
            <StatusBadge status={repo.status} />
          </span>
        }
        actions={
          <button onClick={handleAnalyze} disabled={analyzing} className="btn-secondary">
            {analyzing ? "Analyzing..." : "Analyze"}
          </button>
        }
      />

      <div className="grid grid-cols-3 gap-5 mb-5">
        <div>
          <div className="section-title">URL</div>
          <div className="font-mono text-xs text-fg break-all">{repo.url}</div>
        </div>
        <div>
          <div className="section-title">Status</div>
          <StatusBadge status={repo.status} />
        </div>
        <div>
          <div className="section-title">Created</div>
          <div className="text-sm text-fg-muted">{repo.created_at ? new Date(repo.created_at).toLocaleString() : "—"}</div>
        </div>
      </div>

      {analysis && (
        <div className="grid grid-cols-2 gap-5 mb-5">
          {analysis.languages && Object.keys(analysis.languages).length > 0 && (
            <div>
              <div className="section-title">Languages</div>
              <div className="flex flex-wrap gap-1">
                {Object.entries(analysis.languages).map(([lang]) => (
                  <span key={lang} className="badge-neutral">{lang}</span>
                ))}
              </div>
            </div>
          )}
          {analysis.entry_points && analysis.entry_points.length > 0 && (
            <div>
              <div className="section-title">Entry Points</div>
              <div className="space-y-0.5">
                {analysis.entry_points.map((ep) => (
                  <div key={ep} className="font-mono text-xs text-fg-muted">{ep}</div>
                ))}
              </div>
            </div>
          )}
          {analysis.test_locations && analysis.test_locations.length > 0 && (
            <div>
              <div className="section-title">Test Locations</div>
              <div className="space-y-0.5">
                {analysis.test_locations.map((tl) => (
                  <div key={tl} className="font-mono text-xs text-fg-muted">{tl}</div>
                ))}
              </div>
            </div>
          )}
          {analysis.symbols && analysis.symbols.length > 0 && (
            <div>
              <div className="section-title">Symbols ({analysis.symbols.length})</div>
              <div className="flex flex-wrap gap-1 max-h-[120px] overflow-y-auto">
                {analysis.symbols.slice(0, 30).map((s) => (
                  <span key={`${s.file_path}:${s.name}`} className="font-mono text-[11px] text-fg-muted bg-bg-inset px-1.5 py-0.5 rounded">
                    {s.name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      <div className="divider" />

      <div className="section-title">Create Investigation or Repair</div>
      <div className="mb-3">
        <textarea
          value={issue}
          onChange={(e) => setIssue(e.target.value)}
          placeholder="Describe the issue..."
          className="input min-h-[80px] resize-y"
        />
      </div>
      <div className="flex gap-2">
        <button onClick={handleCreateInvestigation} disabled={creatingInvestigation || !issue.trim()} className="btn-secondary">
          {creatingInvestigation ? "Creating..." : "Investigate"}
        </button>
        <button onClick={handleCreateRepair} disabled={creatingRepair || !issue.trim()} className="btn-primary">
          {creatingRepair ? "Creating..." : "Create Repair"}
        </button>
      </div>
    </div>
  );
}
