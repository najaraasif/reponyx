"use client";

interface HeaderProps {
  title: string;
  subtitle?: React.ReactNode;
  actions?: React.ReactNode;
}

export default function Header({ title, subtitle, actions }: HeaderProps) {
  return (
    <div className="flex items-start justify-between py-4 border-b border-border mb-5">
      <div>
        <h1 className="text-lg font-semibold text-fg">{title}</h1>
        {subtitle && <div className="text-sm text-fg-muted mt-0.5">{subtitle}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </div>
  );
}
