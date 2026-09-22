import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        bg: "#ffffff",
        "bg-subtle": "#f9fafb",
        "bg-inset": "#f3f4f6",
        border: "#e5e7eb",
        "border-subtle": "#f0f0f0",
        fg: "#111827",
        "fg-muted": "#6b7280",
        "fg-subtle": "#9ca3af",
        accent: "#2563eb",
        "accent-hover": "#1d4ed8",
        "accent-subtle": "#eff6ff",
        success: "#16a34a",
        "success-subtle": "#f0fdf4",
        warning: "#d97706",
        "warning-subtle": "#fffbeb",
        danger: "#dc2626",
        "danger-subtle": "#fef2f2",
        mono: "#111827",
      },
      fontFamily: {
        mono: ["ui-monospace", "SFMono-Regular", "SF Mono", "Menlo", "Consolas", "Liberation Mono", "monospace"],
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Noto Sans", "Helvetica", "Arial", "sans-serif"],
      },
      fontSize: {
        xs: ["0.75rem", { lineHeight: "1rem" }],
        sm: ["0.8125rem", { lineHeight: "1.25rem" }],
        base: ["0.875rem", { lineHeight: "1.5rem" }],
      },
      spacing: {
        0: "0",
        0.5: "2px",
        1: "4px",
        1.5: "6px",
        2: "8px",
        2.5: "10px",
        3: "12px",
        3.5: "14px",
        4: "16px",
        5: "20px",
        6: "24px",
        8: "32px",
        10: "40px",
        12: "48px",
      },
      borderRadius: {
        sm: "3px",
        DEFAULT: "4px",
        md: "6px",
      },
      maxWidth: {
        content: "1120px",
      },
    },
  },
  plugins: [],
};

export default config;
