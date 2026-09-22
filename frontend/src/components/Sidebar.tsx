"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

const nav = [
  {
    label: "Navigation",
    items: [
      { href: "/overview", label: "Overview", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" },
      { href: "/repositories", label: "Repositories", icon: "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" },
      { href: "/investigations", label: "Investigations", icon: "M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" },
      { href: "/repairs", label: "Repairs", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" },
      { href: "/review", label: "Review", icon: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/llm", label: "LLM / Providers", icon: "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" },
      { href: "/evaluations", label: "Evaluations", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
      { href: "/settings", label: "Settings", icon: "M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z M15 12a3 3 0 11-6 0 3 3 0 016 0z" },
    ],
  },
];

function Icon({ d }: { d: string }) {
  return (
    <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
      <path strokeLinecap="round" strokeLinejoin="round" d={d} />
    </svg>
  );
}

export default function Sidebar() {
  const pathname = usePathname();
  const [backendOk, setBackendOk] = useState(true);
  const [llmOk, setLlmOk] = useState(true);

  useEffect(() => {
    api.health().then((h) => setBackendOk(h.status === "ok")).catch(() => setBackendOk(false));
    api.llmHealth().then((h) => setLlmOk(h.available)).catch(() => setLlmOk(false));
  }, []);

  const hasWarnings = !backendOk || !llmOk;

  return (
    <aside className="w-[200px] bg-bg border-r border-border flex flex-col h-screen fixed left-0 top-0 z-30">
      <div className="px-3 py-3 border-b border-border">
        <Link href="/overview" className="flex items-center gap-2">
          <div className="w-6 h-6 rounded bg-fg flex items-center justify-center text-bg text-[10px] font-bold">R</div>
          <div>
            <div className="text-sm font-semibold text-fg leading-none">Reponyx</div>
          </div>
        </Link>
      </div>

      <nav className="flex-1 py-2 overflow-y-auto">
        {nav.map((section) => (
          <div key={section.label} className="mb-3">
            <div className="px-3 mb-1 text-[10px] font-medium text-fg-subtle uppercase tracking-wider">{section.label}</div>
            {section.items.map((item) => {
              const active = pathname.startsWith(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center gap-2 px-3 py-1 text-sm transition-colors ${
                    active
                      ? "text-accent bg-accent-subtle"
                      : "text-fg-muted hover:text-fg hover:bg-bg-subtle"
                  }`}
                >
                  <Icon d={item.icon} />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {hasWarnings && (
        <div className="px-3 py-2 border-t border-border space-y-1">
          {!backendOk && (
            <div className="flex items-center justify-between py-0.5 text-[11px]">
              <span className="text-fg-subtle">Backend</span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                <span className="text-warning">Disconnected</span>
              </span>
            </div>
          )}
          {!llmOk && (
            <div className="flex items-center justify-between py-0.5 text-[11px]">
              <span className="text-fg-subtle">LLM</span>
              <span className="flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-warning" />
                <span className="text-warning">Disconnected</span>
              </span>
            </div>
          )}
        </div>
      )}
    </aside>
  );
}
