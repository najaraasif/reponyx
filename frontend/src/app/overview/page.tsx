"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Repository, RepairHistoryItem } from "@/lib/types";

export default function OverviewPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [repairs, setRepairs] = useState<RepairHistoryItem[]>([]);
  const [health, setHealth] = useState<string>("unknown");

  useEffect(() => {
    api.health().then((h) => setHealth(h.status)).catch(() => {});
    api.repositories.list().then(setRepos).catch(() => {});
    api.repairs.list().then(setRepairs).catch(() => {});
  }, []);

  const completed = repairs.filter((r) => r.status === "completed").length;
  const failed = repairs.filter((r) => r.status === "failed").length;
  const pending = repairs.filter((r) => r.status === "pending" || r.status === "running").length;

  return (
    <div className="page">
      <Header title="Overview" subtitle="System status and recent activity" />

      <div className="grid grid-cols-5 gap-3 mb-5">
        <Stat label="Repositories" value={repos.length} />
        <Stat label="Repairs" value={repairs.length} />
        <Stat label="Completed" value={completed} />
        <Stat label="Failed" value={failed} />
        <Stat label="Pending" value={pending} />
      </div>

      <div className="grid grid-cols-2 gap-5">
        <div>
          <div className="section-title">Recent Repairs</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Repository</th>
                  <th>Issue</th>
                </tr>
              </thead>
              <tbody>
                {repairs.slice(0, 5).map((r) => (
                  <tr key={r.repair_id}>
                    <td><StatusBadge status={r.status} /></td>
                    <td className="font-mono text-xs text-fg-muted">{r.repository_id.slice(0, 8)}</td>
                    <td className="max-w-[200px] truncate text-fg-muted">{r.issue?.slice(0, 60) || "—"}</td>
                  </tr>
                ))}
                {repairs.length === 0 && (
                  <tr><td colSpan={3} className="text-fg-subtle text-center py-4">No repairs</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div>
          <div className="section-title">Repositories</div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Repository</th>
                  <th>Created</th>
                </tr>
              </thead>
              <tbody>
                {repos.slice(0, 5).map((r) => (
                  <tr key={r.id}>
                    <td><StatusBadge status={r.status} /></td>
                    <td>
                      <Link href={`/repositories/${r.id}`} className="font-mono text-xs text-accent hover:underline">{r.url.split("/").slice(-2).join("/")}</Link>
                    </td>
                    <td className="text-xs text-fg-muted">{r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td>
                  </tr>
                ))}
                {repos.length === 0 && (
                  <tr><td colSpan={3} className="text-fg-subtle text-center py-4">No repositories</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="mt-5">
        <div className="section-title">System</div>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-fg-muted">Backend</span>
          <span className="flex items-center gap-1.5">
            <span className={`w-1.5 h-1.5 rounded-full ${health === "ok" ? "bg-success" : "bg-danger"}`} />
            <span className="text-fg">{health}</span>
          </span>
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="border border-border rounded-md px-3 py-2">
      <div className="text-[11px] text-fg-muted">{label}</div>
      <div className="text-lg font-semibold text-fg">{value}</div>
    </div>
  );
}
