"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { RepairHistoryItem } from "@/lib/types";

export default function ReviewPage() {
  const [repairs, setRepairs] = useState<RepairHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.repairs.list()
      .then((data) => setRepairs(Array.isArray(data) ? data.filter((r) => r.status === "completed") : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page">
      <Header title="Review" subtitle="Completed repairs awaiting review" />

      {loading ? (
        <div className="space-y-1">
          {[...Array(3)].map((_, i) => <div key={i} className="skeleton h-10 w-full" />)}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Status</th>
                <th>Repair ID</th>
                <th>Repository</th>
                <th>Issue</th>
                <th>Iterations</th>
              </tr>
            </thead>
            <tbody>
              {repairs.map((r) => (
                <tr key={r.repair_id}>
                  <td><StatusBadge status={r.status} /></td>
                  <td>
                    <Link href={`/review/${r.repair_id}`} className="font-mono text-xs text-accent hover:underline">{r.repair_id.slice(0, 12)}</Link>
                  </td>
                  <td className="font-mono text-xs text-fg-muted">{r.repository_id.slice(0, 8)}</td>
                  <td className="text-sm text-fg-muted max-w-[250px] truncate">{r.issue?.slice(0, 60) || "—"}</td>
                  <td className="text-xs text-fg-muted">{r.iterations}</td>
                </tr>
              ))}
              {repairs.length === 0 && (
                <tr><td colSpan={5} className="text-fg-subtle text-center py-8">No completed repairs to review</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
