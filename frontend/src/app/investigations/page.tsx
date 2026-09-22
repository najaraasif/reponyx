"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";

interface Investigation {
  investigation_id: string;
  repository_id: string;
  issue: string;
  status: string;
  created_at: string;
}

export default function InvestigationsPage() {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.investigations
      .list()
      .then((data) => setInvestigations(Array.isArray(data) ? data : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <Header title="Investigations" subtitle="Root cause analysis results" />

      {loading ? (
        <div className="space-y-1">
          {[...Array(5)].map((_, i) => <div key={i} className="skeleton h-10 w-full" />)}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Issue</th>
                <th>Repository</th>
                <th>Created</th>
              </tr>
            </thead>
            <tbody>
              {investigations.map((inv) => (
                <tr key={inv.investigation_id}>
                  <td><StatusBadge status={inv.status} /></td>
                  <td>
                    <Link href={`/investigations/${inv.investigation_id}`} className="text-fg hover:text-accent transition-colors">
                      {inv.issue?.split("\n")[0]?.slice(0, 80) || "—"}
                    </Link>
                  </td>
                  <td className="font-mono text-xs text-fg-muted">{inv.repository_id.slice(0, 8)}</td>
                  <td className="text-xs text-fg-muted">{inv.created_at ? new Date(inv.created_at).toLocaleDateString() : "—"}</td>
                </tr>
              ))}
              {investigations.length === 0 && (
                <tr><td colSpan={4} className="text-fg-subtle text-center py-8">No investigations yet</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
