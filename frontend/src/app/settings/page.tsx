"use client";

import Header from "@/components/Header";

interface SettingGroup {
  title: string;
  settings: { label: string; value: string; description?: string }[];
}

const groups: SettingGroup[] = [
  {
    title: "Execution",
    settings: [
      { label: "Docker Image", value: "reponyx-executor:phase4", description: "Isolated execution environment" },
      { label: "Max Patch Size", value: "50 KB", description: "Maximum allowed patch size" },
      { label: "Timeout", value: "3600s", description: "Maximum execution time per repair" },
    ],
  },
  {
    title: "Security",
    settings: [
      { label: "Immutability", value: "Enabled", description: "Canonical repository is never modified" },
      { label: "Isolation", value: "Docker", description: "Repairs run in isolated containers" },
      { label: "Symlink Protection", value: "Enabled", description: "O_NOFOLLOW on symlinked paths" },
    ],
  },
  {
    title: "Limits",
    settings: [
      { label: "Max Investigations", value: "100", description: "Per repository" },
      { label: "Max Repairs", value: "100", description: "Per repository" },
      { label: "Evidence Limit", value: "50", description: "Items per investigation" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="page">
      <Header title="Settings" subtitle="System configuration" />

      <div className="space-y-5">
        {groups.map((group) => (
          <section key={group.title}>
            <div className="section-title">{group.title}</div>
            <div className="border border-border rounded">
              {group.settings.map((s, i) => (
                <div key={s.label} className={`flex items-center justify-between px-3 py-2 ${i > 0 ? "border-t border-border" : ""}`}>
                  <div>
                    <div className="text-sm text-fg">{s.label}</div>
                    {s.description && <div className="text-xs text-fg-subtle">{s.description}</div>}
                  </div>
                  <div className="font-mono text-xs text-fg-muted">{s.value}</div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}
