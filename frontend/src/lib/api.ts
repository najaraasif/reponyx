import {
  HealthResponse,
  LLMHealthResponse,
  Repository,
  RepositoryAnalysis,
  Investigation,
  InvestigationDetail,
  InvestigationReport,
  Repair,
  RepairReport,
  RepairDiff,
  RepairReview,
  RepairHistoryItem,
  SearchResult,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

class APIError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "APIError";
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...options?.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      const json = JSON.parse(body);
      detail = json.detail || body;
    } catch {}
    throw new APIError(res.status, detail);
  }
  return res.json();
}

export const api = {
  health: () => request<HealthResponse>("/healthz"),
  llmHealth: () => request<LLMHealthResponse>("/llm/health"),

  repositories: {
    list: () => request<Repository[]>("/repositories"),
    get: (id: string) => request<Repository>(`/repositories/${id}`),
    create: (url: string) =>
      request<Repository>("/repositories", {
        method: "POST",
        body: JSON.stringify({ url }),
      }),
    analyze: (id: string) =>
      request<RepositoryAnalysis>(`/repositories/${id}/analyze`, { method: "POST" }),
    structure: (id: string) => request<unknown>(`/repositories/${id}/structure`),
    symbols: (id: string) => request<unknown>(`/repositories/${id}/symbols`),
    dependencies: (id: string) => request<unknown>(`/repositories/${id}/dependencies`),
    search: (id: string, query: string, topK = 8) =>
      request<SearchResult[]>(`/repositories/${id}/search`, {
        method: "POST",
        body: JSON.stringify({ query, top_k: topK }),
      }),
    index: (id: string) =>
      request<unknown>(`/repositories/${id}/index`, { method: "POST" }),
  },

  investigations: {
    list: () => request<Investigation[]>("/investigations"),
    get: (id: string) => request<InvestigationDetail>(`/investigations/${id}`),
    report: (id: string) => request<InvestigationReport>(`/investigations/${id}/report`),
    create: (repoId: string, issue: string) =>
      request<Investigation>(`/repositories/${repoId}/investigations`, {
        method: "POST",
        body: JSON.stringify({ issue }),
      }),
  },

  repairs: {
    list: () => request<RepairHistoryItem[]>("/repairs"),
    get: (id: string) => request<Repair>(`/repairs/${id}`),
    report: (id: string) => request<RepairReport>(`/repairs/${id}/report`),
    diff: (id: string) => request<RepairDiff>(`/repairs/${id}/diff`),
    review: (id: string) => request<RepairReview>(`/repairs/${id}/review`),
    approve: (id: string) =>
      request<unknown>(`/repairs/${id}/approve`, { method: "POST" }),
    reject: (id: string) =>
      request<unknown>(`/repairs/${id}/reject`, { method: "POST" }),
    cancel: (id: string) =>
      request<unknown>(`/repairs/${id}/cancel`, { method: "POST" }),
    create: (repoId: string, issue: string, investigationId?: string) =>
      request<Repair>(`/repositories/${repoId}/repairs`, {
        method: "POST",
        body: JSON.stringify({ issue, investigation_id: investigationId }),
      }),
  },
};

export { APIError };
