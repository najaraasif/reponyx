"use client";

import { useEffect, useState, useMemo } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Header from "@/components/Header";
import StatusBadge from "@/components/StatusBadge";
import { api } from "@/lib/api";
import type { InvestigationDetail, InvestigationReport, EvidenceItem, Hypothesis } from "@/lib/types";

/* ── Root cause parsing ────────────────────────────────────────────── */

interface ParsedRootCause {
  summary: string;
  primaryImpl: string[];
  primaryTests: string[];
  reportedValues: { expected: string; actual: string } | null;
  sourceLocations: string[];
}

function parseRootCause(raw: string | null): ParsedRootCause | null {
  if (!raw) return null;

  const implMatch = raw.match(/Primary implementation:\s*([^;]+)/);
  const testMatch = raw.match(/Primary tests:\s*([^;]+)/);
  const valuesMatch = raw.match(/Reported values:\s*expected=([^,]+),\s*actual=([^\s;]+)/);
  const sourceMatch = raw.match(/Source-inspected:\s*(.+)/);

  const primaryImpl = implMatch
    ? implMatch[1].split(",").map((s) => s.trim()).filter(Boolean)
    : [];
  const primaryTests = testMatch
    ? testMatch[1].split(",").map((s) => s.trim()).filter(Boolean)
    : [];
  const reportedValues = valuesMatch
    ? { expected: valuesMatch[1], actual: valuesMatch[2] }
    : null;
  const sourceLocations = sourceMatch
    ? sourceMatch[1].split(",").map((s) => s.trim()).filter(Boolean)
    : [];

  const issueMatch = raw.match(/Issue:\s*(.+?)(?:;|$)/);
  const summary = issueMatch ? issueMatch[1].trim() : raw.split("\n")[0];

  return { summary, primaryImpl, primaryTests, reportedValues, sourceLocations };
}

/* ── Evidence classification ───────────────────────────────────────── */

function classifyEvidence(
  evidence: EvidenceItem[],
  affectedFiles: string[],
  relevantSymbols: string[]
): Record<string, EvidenceItem[]> {
  const categories: Record<string, EvidenceItem[]> = {
    primary_implementation: [],
    primary_test: [],
    supporting: [],
    unrelated: [],
  };
  const srcFiles = affectedFiles.filter((f) => f.startsWith("src/"));
  const testFiles = affectedFiles.filter((f) => f.startsWith("tests/") || f.startsWith("test/"));

  for (const ev of evidence) {
    if (ev.type === "dependency") continue;
    const isSrc = srcFiles.some((f) => ev.file_path.includes(f));
    const isTest = testFiles.some((f) => ev.file_path.includes(f));
    const hasSymbol = ev.symbol && relevantSymbols.includes(ev.symbol);

    if (isSrc && hasSymbol) categories.primary_implementation.push(ev);
    else if (isTest && hasSymbol) categories.primary_test.push(ev);
    else if (isSrc || isTest || hasSymbol) categories.supporting.push(ev);
    else categories.unrelated.push(ev);
  }
  return categories;
}

/* ── Page ──────────────────────────────────────────────────────────── */

export default function InvestigationDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [detail, setDetail] = useState<InvestigationDetail | null>(null);
  const [report, setReport] = useState<InvestigationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [creatingRepair, setCreatingRepair] = useState(false);

  useEffect(() => {
    Promise.all([
      api.investigations.get(id).catch(() => null),
      api.investigations.report(id).catch(() => null),
    ]).then(([d, r]) => { setDetail(d); setReport(r); }).finally(() => setLoading(false));
  }, [id]);

  const evidence = useMemo(() => report?.evidence || [], [report]);
  const affectedFiles = useMemo(() => report?.affected_files || [], [report]);
  const relevantSymbols = useMemo(() => report?.relevant_symbols || [], [report]);
  const hypotheses = useMemo(() => report?.hypotheses || [], [report]);
  const classifiedEvidence = useMemo(() => report?.classified_evidence || [], [report]);
  const categorized = useMemo(() => {
    if (classifiedEvidence.length > 0) {
      const evidenceMap = new Map(evidence.map((ev) => [ev.evidence_id, ev]));
      const categories: Record<string, EvidenceItem[]> = {
        primary_implementation: [],
        primary_tests: [],
        direct_references: [],
        supporting: [],
        unrelated: [],
      };
      for (const item of classifiedEvidence) {
        const ev = evidenceMap.get(item.evidence_id);
        if (ev) {
          const key = item.category === "primary_implementation" ? "primary_implementation"
            : item.category === "primary_tests" ? "primary_tests"
            : item.category === "direct_references" ? "direct_references"
            : item.category === "supporting" ? "supporting"
            : "unrelated";
          categories[key].push(ev);
        }
      }
      return categories;
    }
    return classifyEvidence(evidence, affectedFiles, relevantSymbols);
  }, [evidence, affectedFiles, relevantSymbols, classifiedEvidence]);
  const parsedRootCause = useMemo(() => parseRootCause(report?.root_cause || null), [report]);

  const firstHyp = hypotheses[0];
  const verificationStatus = firstHyp?.verification_status || "inconclusive";
  const hasRootCause = !!report?.root_cause;
  const repairReady = evidence.length > 0 && hasRootCause && affectedFiles.length > 0 && report?.confidence !== "low";

  async function handleCreateRepair() {
    if (!report?.repository_id) return;
    setCreatingRepair(true);
    try {
      const repair = await api.repairs.create(report.repository_id, report.issue || "Investigation-based repair", id);
      window.location.href = `/repairs/${repair.repair_id}`;
    } catch {}
    setCreatingRepair(false);
  }

  if (loading) {
    return (
      <div className="page">
        <Header title="Investigation" />
        <div className="space-y-3">
          <div className="skeleton h-8 w-full" />
          <div className="skeleton h-24 w-full" />
          <div className="skeleton h-48 w-full" />
        </div>
      </div>
    );
  }

  if (!detail && !report) {
    return (
      <div className="page">
        <Header title="Investigation Not Found" />
        <p className="text-fg-muted">Investigation not found.</p>
        <Link href="/investigations" className="text-accent text-sm hover:underline mt-2 inline-block">Back</Link>
      </div>
    );
  }

  const title = report?.issue?.split("\n")[0]?.replace(/^Title:\s*/i, "") || `Investigation ${id.slice(0, 8)}`;

  return (
    <div className="page">
      {/* ── Header ─────────────────────────────────────────────── */}
      <Header
        title={title}
        subtitle={
          <div className="flex items-center gap-3 text-sm text-fg-muted mt-1">
            {report?.repository_id && (
              <span className="font-mono text-xs text-fg-muted">{report.repository_id.slice(0, 8)}</span>
            )}
            {detail?.status && <StatusBadge status={detail.status} />}
            {report?.confidence && (
              <span className="text-xs">
                Confidence: <span className={`font-medium ${report.confidence === "high" ? "text-success" : report.confidence === "medium" ? "text-warning" : "text-fg-muted"}`}>{report.confidence}</span>
              </span>
            )}
            {firstHyp && (
              <span className="text-xs">
                Verification: <StatusBadge status={verificationStatus} />
              </span>
            )}
          </div>
        }
        actions={
          repairReady && (
            <button onClick={handleCreateRepair} disabled={creatingRepair} className="btn-primary">
              {creatingRepair ? "Creating..." : "Create Repair"}
            </button>
          )
        }
      />

      {/* ── Summary strip ──────────────────────────────────────── */}
      <div className="flex items-center gap-5 text-xs text-fg-muted mb-5 py-2 border-b border-border">
        <span>Evidence: <span className="text-fg font-medium">{evidence.length}</span></span>
        <span>Primary: <span className="text-fg font-medium">{categorized.primary_implementation.length + categorized.primary_tests.length + (categorized.direct_references?.length || 0)}</span></span>
        <span>Files: <span className="text-fg font-medium">{affectedFiles.length}</span></span>
        <span>Symbols: <span className="text-fg font-medium">{relevantSymbols.length}</span></span>
        <span>Repair: <span className={`font-medium ${repairReady ? "text-success" : "text-fg-muted"}`}>{repairReady ? "Ready" : "Not Ready"}</span></span>
      </div>

      <div className="flex gap-6">
        {/* ── Main content ──────────────────────────────────────── */}
        <div className="flex-1 min-w-0">

          {/* Issue */}
          <Section title="Issue">
            <p className="text-sm text-fg leading-relaxed whitespace-pre-wrap">{report?.issue}</p>
          </Section>

          <hr className="divider" />

          {/* Root Cause — primary section */}
          <Section title="Root Cause">
            {parsedRootCause ? (
              <div className="space-y-3">
                <p className="text-sm text-fg leading-relaxed">{parsedRootCause.summary}</p>

                {parsedRootCause.reportedValues && (
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-fg-muted">Expected: <span className="font-mono text-fg font-medium">{parsedRootCause.reportedValues.expected}</span></span>
                    <span className="text-fg-muted">Actual: <span className="font-mono text-fg font-medium">{parsedRootCause.reportedValues.actual}</span></span>
                  </div>
                )}

                {parsedRootCause.primaryImpl.length > 0 && (
                  <div>
                    <span className="text-[11px] text-fg-subtle uppercase tracking-wider">Primary Implementation</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {parsedRootCause.primaryImpl.map((f) => (
                        <span key={f} className="font-mono text-xs text-accent bg-accent/5 px-1.5 py-0.5 rounded">{f}</span>
                      ))}
                    </div>
                  </div>
                )}

                {parsedRootCause.primaryTests.length > 0 && (
                  <div>
                    <span className="text-[11px] text-fg-subtle uppercase tracking-wider">Primary Tests</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {parsedRootCause.primaryTests.map((f) => (
                        <span key={f} className="font-mono text-xs text-accent bg-accent/5 px-1.5 py-0.5 rounded">{f}</span>
                      ))}
                    </div>
                  </div>
                )}

                {parsedRootCause.sourceLocations.length > 0 && (
                  <div>
                    <span className="text-[11px] text-fg-subtle uppercase tracking-wider">Source Locations</span>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {parsedRootCause.sourceLocations.map((loc) => (
                        <span key={loc} className="font-mono text-[11px] text-fg-muted bg-bg-inset px-1.5 py-0.5 rounded">{loc}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-fg-subtle italic">No root cause identified.</p>
            )}
          </Section>

          <hr className="divider" />

          {/* Evidence */}
          <Section title={`Evidence (${evidence.filter((e) => e.type !== "dependency").length} items)`}>
            <EvidenceCategoryTable title="Primary Implementation" items={categorized.primary_implementation} accent />
            <EvidenceCategoryTable title="Primary Tests" items={categorized.primary_tests} accent />
            {categorized.direct_references && categorized.direct_references.length > 0 && (
              <EvidenceCategoryTable title="Direct References" items={categorized.direct_references} />
            )}
            {categorized.supporting.length > 0 && (
              <EvidenceCategoryTable title="Supporting" items={categorized.supporting} />
            )}
            {categorized.unrelated.length > 0 && (
              <EvidenceCategoryTable title="Unrelated" items={categorized.unrelated} collapsed />
            )}
          </Section>

          <hr className="divider" />

          {/* Evidence Chain */}
          <Section title="Evidence Chain">
            <div className="flex items-center gap-0 overflow-x-auto py-1">
              {(["Issue", "Implementation", "Test", "Finding", "Conclusion"] as const).map((step, i, arr) => {
                const isActive = i <= (hasRootCause ? arr.length - 1 : 2);
                return (
                  <div key={step} className="flex items-center shrink-0">
                    <span className={`px-2.5 py-1 rounded text-xs font-medium ${isActive ? "bg-accent/10 text-accent" : "bg-bg-inset text-fg-subtle"}`}>
                      {step}
                    </span>
                    {i < arr.length - 1 && (
                      <svg className="w-4 h-4 text-border mx-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                      </svg>
                    )}
                  </div>
                );
              })}
            </div>
          </Section>

          <hr className="divider" />

          {/* Hypotheses */}
          {hypotheses.length > 0 && (
            <>
              <Section title="Hypotheses">
                <div className="space-y-2">
                  {hypotheses.map((hyp: Hypothesis, i: number) => (
                    <div key={hyp.hypothesis_id || i} className="border border-border rounded p-3">
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="font-mono text-[11px] text-fg-subtle">{hyp.hypothesis_id}</span>
                        <span className="text-[11px] text-fg-muted">Confidence: <span className="text-fg font-medium">{hyp.confidence}</span></span>
                        <StatusBadge status={hyp.verification_status} />
                      </div>
                      <p className="text-sm text-fg leading-relaxed">
                        {hyp.description.length > 400 ? hyp.description.slice(0, 400) + "..." : hyp.description}
                      </p>
                      {hyp.supporting_evidence.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {hyp.supporting_evidence.slice(0, 6).map((eid: string) => (
                            <span key={eid} className="font-mono text-[10px] text-fg-subtle bg-bg-inset px-1.5 py-0.5 rounded">{eid.slice(0, 8)}</span>
                          ))}
                          {hyp.supporting_evidence.length > 6 && (
                            <span className="text-[10px] text-fg-subtle">+{hyp.supporting_evidence.length - 6}</span>
                          )}
                        </div>
                      )}
                      {hyp.contradicting_evidence.length > 0 && (
                        <div className="mt-1 text-[11px] text-danger">
                          {hyp.contradicting_evidence.length} contradicting
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </Section>
              <hr className="divider" />
            </>
          )}

          {/* Affected Files + Symbols */}
          <div className="grid grid-cols-2 gap-5 mb-5">
            <div>
              <div className="section-title">Affected Files</div>
              {affectedFiles.length > 0 ? (
                <div className="space-y-0.5">
                  {affectedFiles.map((f) => (
                    <div key={f} className="font-mono text-xs text-fg bg-bg-inset rounded px-2 py-1">{f}</div>
                  ))}
                </div>
              ) : (
                <EmptyState message="No affected files identified." />
              )}
            </div>
            <div>
              <div className="section-title">Relevant Symbols</div>
              {relevantSymbols.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {relevantSymbols.map((s) => (
                    <span key={s} className="font-mono text-[11px] text-fg-muted bg-bg-inset px-1.5 py-0.5 rounded">{s}</span>
                  ))}
                </div>
              ) : (
                <EmptyState message="No relevant symbols identified." />
              )}
            </div>
          </div>

          {/* Limitations */}
          {report?.limitations && report.limitations.length > 0 && (
            <Section title="Limitations">
              <div className="space-y-1">
                {report.limitations.map((l: string, i: number) => (
                  <div key={i} className="flex items-start gap-1.5 text-xs text-fg-muted">
                    <span className="text-warning mt-0.5 shrink-0">!</span>
                    {l}
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Next Step */}
          {report?.recommended_next_step && (
            <Section title="Recommended Next Step">
              <p className="text-sm text-fg-muted">{report.recommended_next_step}</p>
            </Section>
          )}

          {/* Conclusion */}
          <Section title="Conclusion">
            <div className="flex items-start gap-3">
              {hasRootCause ? (
                <>
                  <div className="w-6 h-6 rounded bg-success/10 flex items-center justify-center shrink-0 mt-0.5">
                    <svg className="w-4 h-4 text-success" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-success">Confirmed Defect</div>
                    <div className="text-xs text-fg-muted mt-0.5">
                      Root cause identified with {report?.confidence || "unknown"} confidence.
                      {repairReady ? " Ready for automated repair." : " Manual repair may be needed."}
                    </div>
                  </div>
                </>
              ) : evidence.length > 0 ? (
                <>
                  <div className="w-6 h-6 rounded bg-warning/10 flex items-center justify-center shrink-0 mt-0.5">
                    <svg className="w-4 h-4 text-warning" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-warning">Insufficient Evidence</div>
                    <div className="text-xs text-fg-muted mt-0.5">Evidence collected but root cause not determined.</div>
                  </div>
                </>
              ) : (
                <>
                  <div className="w-6 h-6 rounded bg-bg-inset flex items-center justify-center shrink-0 mt-0.5">
                    <svg className="w-4 h-4 text-fg-subtle" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M18.364 18.364A9 9 0 005.636 5.636m12.728 12.728A9 9 0 015.636 5.636m12.728 12.728L5.636 5.636" />
                    </svg>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-fg-muted">No Defect Found</div>
                    <div className="text-xs text-fg-muted mt-0.5">No evidence of a defect was found.</div>
                  </div>
                </>
              )}
            </div>
          </Section>

          <hr className="divider" />

          {/* Repair Readiness */}
          <Section title="Repair Readiness">
            <div className="border border-border rounded p-3">
              <div className="space-y-1.5 mb-3">
                <CheckItem checked={evidence.length > 0} label="Evidence collected" />
                <CheckItem checked={hasRootCause} label="Root cause identified" />
                <CheckItem checked={affectedFiles.length > 0} label={`Affected files (${affectedFiles.length})`} />
              </div>
              {repairReady ? (
                <button onClick={handleCreateRepair} disabled={creatingRepair} className="btn-primary">
                  {creatingRepair ? "Creating..." : "Create Repair"}
                </button>
              ) : (
                <p className="text-xs text-fg-subtle">Insufficient evidence for automated repair.</p>
              )}
            </div>
          </Section>
        </div>

        {/* ── Right sidebar ─────────────────────────────────────── */}
        <aside className="w-[200px] shrink-0">
          <div className="sticky top-4 space-y-4">
            <SidebarSection title="Investigation">
              <MetaRow label="Status" value={detail?.status || "—"} />
              <MetaRow label="Confidence" value={report?.confidence || "—"} />
              <MetaRow label="Evidence" value={`${evidence.length} items`} />
              <MetaRow label="Files" value={`${affectedFiles.length}`} />
              <MetaRow label="Symbols" value={`${relevantSymbols.length}`} />
              <MetaRow label="Repair" value={repairReady ? "Ready" : "Not Ready"} />
            </SidebarSection>
            <SidebarSection title="Repository">
              <div className="font-mono text-xs text-fg-muted break-all">{report?.repository_id || "—"}</div>
            </SidebarSection>
            <SidebarSection title="Investigation ID">
              <div className="font-mono text-[11px] text-fg-subtle break-all">{id}</div>
            </SidebarSection>
          </div>
        </aside>
      </div>
    </div>
  );
}

/* ── Helper components ─────────────────────────────────────────────── */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-5">
      <div className="section-title">{title}</div>
      {children}
    </section>
  );
}

function SidebarSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="section-title">{title}</div>
      <div className="space-y-1.5 text-sm">{children}</div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-fg-muted">{label}</span>
      <span className="text-fg font-medium text-xs">{value}</span>
    </div>
  );
}

function CheckItem({ checked, label }: { checked: boolean; label: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <div className={`w-3.5 h-3.5 rounded border flex items-center justify-center ${checked ? "bg-success border-success text-white" : "border-border"}`}>
        {checked && (
          <svg className="w-2.5 h-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
          </svg>
        )}
      </div>
      <span className={checked ? "text-fg" : "text-fg-muted"}>{label}</span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return <p className="text-sm text-fg-subtle italic">{message}</p>;
}

function EvidenceCategoryTable({ title, items, accent = false, collapsed = false }: {
  title: string;
  items: EvidenceItem[];
  accent?: boolean;
  collapsed?: boolean;
}) {
  const [open, setOpen] = useState(!collapsed);

  if (items.length === 0) return null;

  return (
    <div className="mb-3">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-xs font-medium text-fg-muted mb-1 hover:text-fg transition-colors"
      >
        <svg className={`w-3 h-3 transition-transform ${open ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        <span className={accent ? "text-fg font-semibold" : ""}>{title}</span>
        <span className="text-fg-subtle">({items.length})</span>
      </button>
      {open && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>File</th>
                <th>Lines</th>
                <th>Symbol</th>
                <th>Description</th>
              </tr>
            </thead>
            <tbody>
              {items.map((ev, i) => (
                <EvidenceRow key={ev.evidence_id || i} ev={ev} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function EvidenceRow({ ev }: { ev: EvidenceItem }) {
  const [expanded, setExpanded] = useState(false);
  const location = ev.file_path
    ? `${ev.file_path}${ev.start_line ? `:${ev.start_line}` : ""}${ev.end_line && ev.end_line !== ev.start_line ? `-${ev.end_line}` : ""}`
    : null;

  return (
    <>
      <tr
        className="cursor-pointer hover:bg-bg-subtle transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="text-xs">{ev.type.replace(/_/g, " ")}</td>
        <td className="font-mono text-xs text-accent">{ev.file_path}</td>
        <td className="font-mono text-xs text-fg-muted">{ev.start_line}{ev.end_line && ev.end_line !== ev.start_line ? `-${ev.end_line}` : ""}</td>
        <td className="font-mono text-xs text-fg-muted">{ev.symbol || "—"}</td>
        <td className="text-xs text-fg-muted max-w-[200px] truncate">{ev.description}</td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={5} className="bg-bg-inset px-3 py-2">
            <div className="space-y-1">
              {location && (
                <div className="text-[11px] text-fg-muted">
                  Location: <span className="font-mono text-fg">{location}</span>
                </div>
              )}
              {ev.symbol && (
                <div className="text-[11px] text-fg-muted">
                  Symbol: <span className="font-mono text-fg">{ev.symbol}</span>
                </div>
              )}
              <div className="text-[11px] text-fg-muted">
                Evidence ID: <span className="font-mono text-fg-subtle">{ev.evidence_id.slice(0, 16)}...</span>
              </div>
              {ev.description && (
                <div className="text-[11px] text-fg-muted mt-1">{ev.description}</div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
