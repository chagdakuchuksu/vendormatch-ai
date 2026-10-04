// Thin wrapper around the VendorMatch REST API. All scoring happens on the server.

export class ApiError extends Error {
  constructor(status, code, message, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(path, {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network_error", "The API could not be reached. Is the server running?");
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    const err = data?.error ?? {};
    throw new ApiError(response.status, err.code ?? "http_error", err.message ?? `Request failed (${response.status}).`, err.details);
  }
  return data;
}

export const api = {
  health: () => request("GET", "/api/health"),
  scoringModel: () => request("GET", "/api/scoring-model"),
  loadDemo: () => request("POST", "/api/demo"),
  listProjects: () => request("GET", "/api/projects"),
  getProject: (id) => request("GET", `/api/projects/${id}`),
  createProject: (data) => request("POST", "/api/projects", data),
  updateProject: (id, data) => request("PUT", `/api/projects/${id}`, data),
  deleteProject: (id) => request("DELETE", `/api/projects/${id}`),
  listVendors: (projectId) => request("GET", `/api/projects/${projectId}/vendors`),
  getVendor: (id) => request("GET", `/api/vendors/${id}`),
  createVendor: (projectId, data) => request("POST", `/api/projects/${projectId}/vendors`, data),
  updateVendor: (id, data) => request("PUT", `/api/vendors/${id}`, data),
  deleteVendor: (id) => request("DELETE", `/api/vendors/${id}`),
  analysis: (projectId) => request("GET", `/api/projects/${projectId}/analysis`),
  comparison: (projectId) => request("GET", `/api/projects/${projectId}/comparison`),
};
