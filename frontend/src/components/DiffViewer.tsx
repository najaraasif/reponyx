"use client";

function parseDiff(diff: string) {
  const lines = diff.split("\n");
  const files: { name: string; additions: number; deletions: number; lines: { type: string; content: string }[] }[] = [];
  let current: (typeof files)[0] | null = null;

  for (const line of lines) {
    if (line.startsWith("diff --git")) {
      if (current) files.push(current);
      const name = line.replace("diff --git a/", "").replace(" b/", "");
      current = { name, additions: 0, deletions: 0, lines: [] };
    } else if (current) {
      if (line.startsWith("+") && !line.startsWith("+++")) {
        current.additions++;
        current.lines.push({ type: "add", content: line });
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        current.deletions++;
        current.lines.push({ type: "del", content: line });
      } else if (line.startsWith("@@")) {
        current.lines.push({ type: "hunk", content: line });
      } else if (line.startsWith("+++") || line.startsWith("---")) {
        // skip
      } else {
        current.lines.push({ type: "ctx", content: line });
      }
    }
  }
  if (current) files.push(current);
  return files;
}

export default function DiffViewer({ diff }: { diff: string }) {
  if (!diff) return <p className="text-fg-subtle text-sm">No diff available.</p>;

  const files = parseDiff(diff);

  return (
    <div className="space-y-3">
      {files.map((file, i) => (
        <div key={i} className="border border-border rounded overflow-hidden">
          <div className="flex items-center justify-between px-3 py-1.5 bg-bg-inset border-b border-border">
            <span className="font-mono text-xs text-fg">{file.name}</span>
            <span className="font-mono text-xs">
              <span className="text-success">+{file.additions}</span>
              <span className="text-fg-subtle mx-1">/</span>
              <span className="text-danger">-{file.deletions}</span>
            </span>
          </div>
          <pre className="overflow-x-auto text-xs leading-relaxed">
            {file.lines.map((line, j) => (
              <div
                key={j}
                className={`px-3 py-0.5 ${
                  line.type === "add"
                    ? "bg-success/5 text-success"
                    : line.type === "del"
                      ? "bg-danger/5 text-danger"
                      : line.type === "hunk"
                        ? "bg-accent/5 text-accent"
                        : "text-fg-muted"
                }`}
              >
                {line.content}
              </div>
            ))}
          </pre>
        </div>
      ))}
    </div>
  );
}
