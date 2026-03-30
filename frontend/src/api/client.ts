const BASE = "/api";

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("pdf-editor-token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = { ...getAuthHeader(), ...init?.headers };
  const res = await fetch(`${BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    localStorage.removeItem("pdf-editor-token");
    localStorage.removeItem("pdf-editor-user");
    window.location.reload();
    throw new Error("Sessão expirada");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// --- Auth ---

export interface LoginResult {
  token: string;
  name: string;
  email: string;
  role: string;
}

export async function login(body: { email: string; password: string }): Promise<LoginResult> {
  const res = await fetch(`${BASE}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Erro ao fazer login" }));
    throw new Error(data.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export interface UploadResult {
  file_id: string;
  filename: string;
  size_bytes: number;
  pages?: number;
  bookmarks?: { level: number; title: string; page: number }[];
}

export interface OperationResult {
  result_file_id: string;
  filename: string;
  size_bytes: number;
  [key: string]: unknown;
}

// --- Files ---

export async function uploadFiles(files: File[]): Promise<UploadResult[]> {
  const form = new FormData();
  for (const f of files) form.append("files", f);
  return request<UploadResult[]>("/upload", { method: "POST", body: form });
}

export function downloadUrl(fileId: string): string {
  return `${BASE}/download/${fileId}`;
}

export async function getMetadata(fileId: string) {
  return request<UploadResult & { pages: number }>(`/metadata/${fileId}`);
}

// --- Operations ---

export async function merge(body: {
  file_ids: string[];
  optimize?: boolean;
  password?: string;
}) {
  return request<OperationResult>("/merge", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function split(body: {
  file_id: string;
  mode: "count" | "size" | "bookmark";
  value: number;
  optimize?: boolean;
}) {
  return request<OperationResult & { parts: number }>("/split", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function extract(body: {
  file_id: string;
  pages?: string;
  page_indices?: number[];
  optimize?: boolean;
  password?: string;
  as_zip?: boolean;
  segments?: { name: string; start: number; end: number }[];
}) {
  return request<OperationResult>("/extract", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function remove(body: {
  file_id: string;
  pages?: string;
  page_indices?: number[];
  optimize?: boolean;
  password?: string;
}) {
  return request<OperationResult & { pages_removed: number; pages_remaining: number }>("/remove", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function rotate(body: {
  file_id: string;
  rotations: Record<number, number>;
  optimize?: boolean;
}) {
  return request<OperationResult>("/rotate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function optimize(body: {
  file_id: string;
  profile?: string;
  password?: string;
  remove_annotations?: boolean;
  metadata?: Record<string, string>;
}) {
  return request<OperationResult & { original_size_bytes: number; reduction_percent: number }>("/optimize", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function bates(body: {
  file_id: string;
  text_pattern?: string;
  start_doc_idx?: number;
  start_page_idx?: number;
  position?: string;
  margin?: number;
  font_size?: number;
  color?: [number, number, number];
}) {
  return request<OperationResult>("/bates", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function redact(body: {
  file_id: string;
  keywords?: string[];
  ignore_case?: boolean;
  patterns?: string[];
}) {
  return request<OperationResult & { redactions_applied: number }>("/redact", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface ScanPiece {
  id: string;
  display_text: string;
  start_page_0_idx: number;
  end_page_0_idx: number;
  title: string;
  category?: string;
  unique_id?: string;
  preselect?: boolean;
  source: string;
}

export async function scan(fileId: string) {
  return request<{
    file_id: string;
    page_count: number;
    pieces: ScanPiece[];
    bookmarks: unknown[];
  }>(`/scan?file_id=${fileId}`, { method: "POST" });
}

export async function diff(body: { file_id_a: string; file_id_b: string }) {
  const res = await fetch(`${BASE}/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...getAuthHeader() },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error("Falha ao comparar PDFs");
  return res.text();
}

export async function imagesToPdf(body: {
  file_ids: string[];
  optimize?: boolean;
}) {
  return request<OperationResult>("/images-to-pdf", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface Thumbnail {
  page: number;
  width: number;
  height: number;
  data: string;
}

export async function getThumbnails(
  fileId: string,
  pageStart = 0,
  pageEnd = 9,
  dpi = 72
) {
  return request<{ file_id: string; thumbnails: Thumbnail[] }>(
    `/thumbnails/${fileId}?page_start=${pageStart}&page_end=${pageEnd}&dpi=${dpi}`
  );
}
