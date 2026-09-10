/**
 * API client for the DevOps MCP Platform backend.
 *
 * Talks DIRECTLY to the FastAPI backend at NEXT_PUBLIC_API_URL
 * (default: http://localhost:8000). No Next.js rewrite proxy — the
 * browser makes the call, CORS allows it.
 */

function resolveBase(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL;
  if (envUrl && !envUrl.includes("backend:")) {
    return envUrl.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    return `http://${host}:8000`;
  }
  return "http://localhost:8000";
}

const BASE = resolveBase();
export const API_BASE_URL = BASE;

// ---------------------------------------------------------------------
// Auth token handling
// ---------------------------------------------------------------------
const TOKEN_KEY = "devops-mcp-token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

// ---------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------
export type TaskStatus =
  | "pending"
  | "running"
  | "success"
  | "failed"
  | "blocked"
  | "dry_run";

export type UserRole = "admin" | "developer" | "viewer";

export interface User {
  id: number;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface IntentResult {
  intent: string;
  confidence: number;
  entities: Record<string, unknown>;
  matched_pattern?: string | null;
  source: "regex" | "llm" | "cache" | "none";
  tokens_used: number;
  latency_ms: number;
}

export interface ToolCall {
  tool_name: string;
  params: Record<string, unknown>;
}

export interface ExecuteResponse {
  task_id: number;
  status: TaskStatus;
  intent?: IntentResult;
  tool_call?: ToolCall;
  result?: {
    success: boolean;
    summary: string;
    data: Record<string, unknown>;
    stdout: string;
    stderr: string;
    warnings: string[];
  };
  summary?: string;
  duration_ms?: number;
  error?: string;
  warnings: string[];
}

export interface TaskOut {
  id: number;
  command: string;
  status: TaskStatus;
  detected_intent: string | null;
  intent_confidence: number | null;
  selected_tool: string | null;
  duration_ms: number | null;
  dry_run: boolean;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface ToolSchema {
  name: string;
  description: string;
  input_schema: Record<string, unknown>;
  intents: string[];
  destructive: boolean;
  category: string;
}

export interface ContainerInfo {
  id: string;
  name: string;
  image: string;
  status: string;
  ports: Record<string, unknown>;
  managed?: boolean;
  created?: string;
}

export interface ContainerActionResponse {
  task_id: number;
  success: boolean;
  summary: string;
  data: Record<string, unknown>;
}

// ---------------------------------------------------------------------
// Core request helper
// ---------------------------------------------------------------------
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...options, headers });
  } catch (networkErr) {
    const msg =
      networkErr instanceof Error ? networkErr.message : String(networkErr);
    throw new Error(
      `Network error reaching ${BASE}${path}: ${msg}. Is the backend running at ${BASE}?`
    );
  }

  if (res.status === 401) {
    // Token expired or invalid — clear it and let the caller redirect.
    setToken(null);
  }

  if (!res.ok) {
    let text = "";
    try {
      text = await res.text();
    } catch {
      /* ignore */
    }
    let detail = text;
    try {
      const parsed = JSON.parse(text);
      if (parsed?.detail) detail = parsed.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail || `HTTP ${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------
// Auth endpoints
// ---------------------------------------------------------------------
export async function login(
  username: string,
  password: string
): Promise<{ access_token: string; expires_in: number }> {
  // OAuth2PasswordRequestForm expects x-www-form-urlencoded
  const form = new URLSearchParams();
  form.set("username", username);
  form.set("password", password);
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: form.toString(),
  });
  if (!res.ok) {
    let msg = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      msg = body?.detail || msg;
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function register(payload: {
  username: string;
  email: string;
  password: string;
  role?: UserRole;
}): Promise<User> {
  return request<User>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ role: "developer", ...payload }),
  });
}

export async function fetchMe(): Promise<User> {
  return request<User>("/auth/me");
}

export function logout() {
  setToken(null);
}

// ---------------------------------------------------------------------
// App endpoints
// ---------------------------------------------------------------------
export async function executeCommand(
  command: string,
  opts: { dry_run?: boolean; confirm_destructive?: boolean } = {}
): Promise<ExecuteResponse> {
  return request<ExecuteResponse>("/execute", {
    method: "POST",
    body: JSON.stringify({
      command,
      dry_run: opts.dry_run ?? false,
      confirm_destructive: opts.confirm_destructive ?? false,
    }),
  });
}

export async function fetchTasks(
  page = 1,
  pageSize = 20
): Promise<{ total: number; items: TaskOut[] }> {
  return request(`/tasks/?page=${page}&page_size=${pageSize}`);
}

export async function fetchTools(): Promise<{
  total: number;
  tools: ToolSchema[];
}> {
  return request("/tools/");
}

export async function fetchHealth(): Promise<{
  status: string;
  version: string;
  checks: Record<string, string>;
}> {
  return request("/health");
}

// ---------------------------------------------------------------------
// Container endpoints (direct, ID-based)
// ---------------------------------------------------------------------
export async function fetchContainers(): Promise<{
  total: number;
  containers: ContainerInfo[];
}> {
  return request("/containers/");
}

export async function stopContainer(id: string): Promise<ContainerActionResponse> {
  return request<ContainerActionResponse>(
    `/containers/${encodeURIComponent(id)}/stop`,
    { method: "POST" }
  );
}

export async function removeContainer(id: string): Promise<ContainerActionResponse> {
  return request<ContainerActionResponse>(
    `/containers/${encodeURIComponent(id)}`,
    { method: "DELETE" }
  );
}
