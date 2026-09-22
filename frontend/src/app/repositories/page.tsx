"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { Repository } from "@/lib/types";

export default function RepositoriesPage() {
  const [repos, setRepos] = useState<Repository[]>([]);
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.repositories.list().then(setRepos).catch(() => {});
  }, []);

  async function handleAdd() {
    if (!url.trim()) return;
    setLoading(true);
    try {
      const repo = await api.repositories.create(url.trim());
      setRepos((prev) => [repo, ...prev]);
      setUrl("");
    } catch {}
    setLoading(false);
  }

  return (
    <div className="page">
      <Header
        title="Repositories"
        subtitle="Manage ingested repositories"
        actions={
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              placeholder="GitHub URL"
              className="input-mono w-[320px]"
            />
            <button onClick={handleAdd} disabled={loading || !url.trim()} className="btn-primary">
              {loading ? "Adding..." : "Add"}
            </button>
          </div>
        }
      />

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Status</th>
              <th>Repository</th>
              <th>ID</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {repos.map((r) => (
              <tr key={r.id}>
                <td><StatusBadge status={r.status} /></td>
                <td>
                  <Link href={`/repositories/${r.id}`} className="text-accent hover:underline">
                    {r.url.split("/").slice(-2).join("/")}
                  </Link>
                </td>
                <td className="font-mono text-xs text-fg-muted">{r.id.slice(0, 12)}</td>
                <td className="text-xs text-fg-muted">{r.created_at ? new Date(r.created_at).toLocaleDateString() : "—"}</td>
              </tr>
            ))}
            {repos.length === 0 && (
              <tr><td colSpan={4} className="text-fg-subtle text-center py-8">No repositories. Add a GitHub URL above.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
