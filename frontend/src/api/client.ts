function apiBase(): string {
  const configured = import.meta.env.VITE_API_BASE_URL;
  if (configured) return configured.replace(/\/$/, "");
  return import.meta.env.DEV ? "http://localhost:8000" : "";
}

const API = apiBase();

export function getToken(): string | null {
  return localStorage.getItem("ruleops_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("ruleops_token", token);
  else localStorage.removeItem("ruleops_token");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API}/api/v1${path}`, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(data.message || `Request failed (${res.status})`) as Error & {
      code?: string;
      context?: unknown;
      retryable?: boolean;
    };
    err.code = data.code;
    err.context = data.context;
    err.retryable = data.retryable;
    throw err;
  }
  return data as T;
}

export const AuthAPI = {
  login: (email: string, password: string) =>
    api<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  me: () => api<{ id: string; email: string; full_name: string; roles: string[]; department: string }>("/auth/me"),
};

export const TicketsAPI = {
  list: (params = "") => api<any[]>(`/tickets${params}`),
  get: (id: string) => api<any>(`/tickets/${id}`),
  create: (body: unknown) => api<any>("/tickets", { method: "POST", body: JSON.stringify(body) }),
  process: (id: string) => api<any>(`/tickets/${id}/process`, { method: "POST" }),
  clarify: (id: string, note: string) =>
    api<any>(`/tickets/${id}/clarify`, { method: "POST", body: JSON.stringify({ note }) }),
};

export const RulesAPI = {
  list: (q = "") => api<any[]>(`/rules${q}`),
  get: (id: string) => api<any>(`/rules/${id}`),
  versions: (id: string) => api<any[]>(`/rules/${id}/versions`),
  resolve: (body: unknown) => api<any>("/rules/resolve", { method: "POST", body: JSON.stringify(body) }),
  execute: (body: unknown) => api<any>("/rules/execute", { method: "POST", body: JSON.stringify(body) }),
};

export const ProposalsAPI = {
  validate: (id: string) => api<any>(`/proposals/${id}/validate`, { method: "POST" }),
  test: (id: string) => api<any>(`/proposals/${id}/test`, { method: "POST" }),
};

export const ApprovalsAPI = {
  list: () => api<any[]>("/approvals"),
  approve: (id: string, comment: string, deploy = false) =>
    api<any>(`/approvals/${id}/approve`, { method: "POST", body: JSON.stringify({ comment, deploy }) }),
  reject: (id: string, comment: string) =>
    api<any>(`/approvals/${id}/reject`, { method: "POST", body: JSON.stringify({ comment }) }),
  requestChange: (id: string, comment: string) =>
    api<any>(`/approvals/${id}/request-change`, { method: "POST", body: JSON.stringify({ comment }) }),
};

export const DeployAPI = {
  list: () => api<any[]>("/deployments"),
  rollback: (id: string, body: unknown) =>
    api<any>(`/deployments/${id}/rollback`, { method: "POST", body: JSON.stringify(body) }),
  deployProposal: (id: string) => api<any>(`/proposals/${id}/deploy`, { method: "POST" }),
};

export const ConfigAPI = {
  list: (params = "") => api<any>(`/configurations${params}`),
  get: (id: string) => api<any>(`/configurations/${id}`),
  resolve: (body: unknown) =>
    api<any>("/configurations/resolve", { method: "POST", body: JSON.stringify(body) }),
  async exportCsv() {
    const res = await fetch(`${API}/api/v1/configurations/export.csv`, {
      headers: { Authorization: `Bearer ${getToken()}` },
    });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },
  async importCsv(file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API}/api/v1/configurations/import`, {
      method: "POST",
      headers: { Authorization: `Bearer ${getToken()}` },
      body: form,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.message || "Import failed");
    return data as { imported: number; updated: number; control_count: string };
  },
};

export const PlatformAPI = {
  dashboard: () => api<any>("/analytics/dashboard"),
  audit: () => api<any[]>("/audit"),
  integrations: () => api<any[]>("/integrations"),
  testRuns: () => api<any[]>("/test-runs"),
  testRun: (id: string) => api<any>(`/test-runs/${id}`),
  citations: () => api<any[]>("/citations"),
};

export function sseUrl(ticketId: string) {
  const base = import.meta.env.VITE_SSE_BASE_URL || API;
  return `${base}/api/v1/events/stream/${ticketId}`;
}
