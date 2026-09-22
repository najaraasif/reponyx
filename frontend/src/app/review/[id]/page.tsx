"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import DiffViewer from "@/components/DiffViewer";
import { api } from "@/lib/api";
import type { RepairReview } from "@/lib/types";

export default function ReviewDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [review, setReview] = useState<RepairReview | null>(null);
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);
  const [confirmAction, setConfirmAction] = useState<"approve" | "reject" | null>(null);

  useEffect(() => {
    api.repairs.review(id).then(setReview).catch(() => {}).finally(() => setLoading(false));
  }, [id]);

  async function handleAction(action: "approve" | "reject") {
    setActing(true);
    try {
      if (action === "approve") await api.repairs.approve(id);
      else await api.repairs.reject(id);
      window.location.reload();
    } catch {}
    setActing(false);
    setConfirmAction(null);
  }

  if (loading) {
    return (
      <div className="page">
        <Header title="Review" />
        <div className="skeleton h-48 w-full" />
      </div>
    );
  }

  if (!review) {
    return (
      <div className="page">
        <Header title="Review Not Found" />
        <p className="text-fg-muted">Repair not found for review.</p>
      </div>
    );
  }

  const r = review.report;

  return (
    <div className="page">
      <Header
        title={`Review ${id.slice(0, 12)}`}
        subtitle={
          <span className="flex items-center gap-2 text-sm text-fg-muted">
            <span className="font-mono text-xs">{r.repository_id?.slice(0, 8)}</span>
            <StatusBadge status={r.status} />
          </span>
        }
        actions={
          !confirmAction ? (
            <div className="flex gap-2">
              <button onClick={() => setConfirmAction("reject")} className="btn-danger">Reject</button>
              <button onClick={() => setConfirmAction("approve")} className="btn-primary">Approve</button>
            </div>
          ) : (
            <div className="flex items-center gap-2">
              <span className="text-sm text-fg-muted">
                {confirmAction === "approve" ? "Approve this repair?" : "Reject this repair?"}
              </span>
              <button onClick={() => setConfirmAction(null)} className="btn-ghost">Cancel</button>
              <button
                onClick={() => handleAction(confirmAction)}
                disabled={acting}
                className={confirmAction === "approve" ? "btn-primary" : "btn-danger"}
              >
                {acting ? "Processing..." : `Confirm ${confirmAction}`}
              </button>
            </div>
          )
        }
      />

      <div className="space-y-5">
        <section>
          <div className="section-title">Issue</div>
          <p className="text-sm text-fg whitespace-pre-wrap">{r.issue}</p>
        </section>

        {r.root_cause && (
          <section>
            <div className="section-title">Root Cause</div>
            <p className="text-sm text-fg">{r.root_cause}</p>
          </section>
        )}

        {r.patch_description && (
          <section>
            <div className="section-title">Patch Description</div>
            <p className="text-sm text-fg-muted">{r.patch_description}</p>
          </section>
        )}

        {r.changed_files && r.changed_files.length > 0 && (
          <section>
            <div className="section-title">Changed Files</div>
            <div className="space-y-0.5">
              {r.changed_files.map((f) => (
                <div key={f} className="font-mono text-xs text-fg bg-bg-inset rounded px-2 py-1">{f}</div>
              ))}
            </div>
          </section>
        )}

        {review.diff && (
          <section>
            <div className="section-title">Diff</div>
            <DiffViewer diff={review.diff} />
          </section>
        )}

        {r.test_results && r.test_results.length > 0 && (
          <section>
            <div className="section-title">Test Results</div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Framework</th>
                    <th>Passed</th>
                    <th>Failed</th>
                    <th>Skipped</th>
                  </tr>
                </thead>
                <tbody>
                  {r.test_results.map((t, i) => (
                    <tr key={i}>
                      <td className="font-mono text-xs">{t.framework}</td>
                      <td className="text-success">{t.passed}</td>
                      <td className="text-danger">{t.failed}</td>
                      <td className="text-fg-subtle">{t.skipped}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {r.final_report && (
          <section>
            <div className="section-title">Final Report</div>
            <p className="text-sm text-fg-muted">{r.final_report}</p>
          </section>
        )}
      </div>
    </div>
  );
}
