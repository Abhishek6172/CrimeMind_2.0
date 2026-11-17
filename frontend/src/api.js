// Thin API client. The token lives in memory + sessionStorage only; the server is the sole authority on access.
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
  try {
    res = await fetch(`/api${path}${qs}`, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, { error: { message: "Cannot reach the server. Check that the API is running." } });
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (res.status === 401 && path !== "/auth/login") { onUnauthorized(); }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export async function apiUpload(path, formData) {
  let res;
  try {
    res = await fetch(`/api${path}`, {
      method: "POST",
      headers: { ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: formData,
    });
  } catch {
    throw new ApiError(0, { error: { message: "Cannot reach the server. Check that the API is running." } });
  }
  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch {}
  if (res.status === 401 && path !== "/auth/login") { onUnauthorized(); }
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

export const caseApi = (ref) => ({
  ref,
  get: (p, params) => api(`/cases/${ref}${p}`, { params }),
  post: (p, body) => api(`/cases/${ref}${p}`, { method: "POST", body: body || {} }),
});
