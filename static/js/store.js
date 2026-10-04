// Caches the data needed to show one project (project, vendors, comparison, analysis).
// Analysis is computed by the server from current data; "Refresh" re-requests it.

import { api } from "./api.js";

const bundles = new Map();

export function loadProjectBundle(projectId, { refresh = false } = {}) {
  const key = String(projectId);
  if (refresh) bundles.delete(key);
  if (!bundles.has(key)) {
    const promise = Promise.all([
      api.getProject(projectId),
      api.listVendors(projectId),
      api.comparison(projectId),
      api.analysis(projectId),
    ]).then(([project, vendors, comparison, analysis]) => ({ project, vendors, comparison, analysis }));
    promise.catch(() => bundles.delete(key)); // never cache failures
    bundles.set(key, promise);
  }
  return bundles.get(key);
}

export function clearProjectBundles() {
  bundles.clear();
}
