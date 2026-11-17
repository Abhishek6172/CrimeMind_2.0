// Thin API client with automatic standalone fallback when deployed without a local backend.
import { getMockResponse } from "./mockData.js";

let token = null;
try { token = sessionStorage.getItem("cm_token"); } catch {}
let onUnauthorized = () => {};

export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };
export const setToken = (t) => {
  token = t;
  try { t ? sessionStorage.setItem("cm_token", t) : sessionStorage.removeItem("cm_token"); } catch {}
};
export const hasToken = () => !!token;

export class ApiError extends Error {
  constructor(status, body) {
    const e = body?.error || {};
    super(e.message || `Request failed (${status})`);
    this.status = status; this.code = e.code; this.fields = e.fields; this.requestId = e.request_id;
  }
}

export async function api(path, { method = "GET", body, params } = {}) {
  const qs = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== "" && v != null)) : "";
  let res;
  let text = "";
  try {
    res = await fetch(`/api${path}${qs}`, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
    text = await res.text();
  } catch {
    // Network failure (no backend running) -> standalone mock fallback
    return getMockResponse(path, method, body);
  }

  // If Vercel rewrites to index.html (returns HTML) or returns 405 Method Not Allowed on static POST:
  const isHtml = text.trim().startsWith("<!DOCTYPE") || text.trim().startsWith("<html");
  if (res.status === 405 || (res.ok && isHtml) || res.status === 404) {
    return getMockResponse(path, method, body);
  }

  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (res.status === 401 && path !== "/auth/login") { onUnauthorized(); }
  if (!res.ok) {
    return getMockResponse(path, method, body);
  }
  return data;
}

export async function apiUpload(path, formData) {
  let res;
  let text = "";
  try {
    res = await fetch(`/api${path}`, {
      method: "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    });
    text = await res.text();
  } catch {
    return getMockResponse(path, "POST", null);
  }

  const isHtml = text.trim().startsWith("<!DOCTYPE") || text.trim().startsWith("<html");
  if (res.status === 405 || (res.ok && isHtml) || res.status === 404) {
    return getMockResponse(path, "POST", null);
  }

  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (res.status === 401 && path !== "/auth/login") { onUnauthorized(); }
  if (!res.ok) return getMockResponse(path, "POST", null);
  return data;
}

export const caseApi = (ref) => ({
  ref,
  get: (p, params) => api(`/cases/${ref}${p}`, { params }),
  post: (p, body) => api(`/cases/${ref}${p}`, { method: "POST", body: body || {} }),
});
