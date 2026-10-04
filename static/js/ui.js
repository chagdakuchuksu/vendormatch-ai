// Formatting helpers and small HTML components. Every API string goes through esc().

const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ESCAPES[c]);
export const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "");
export const fixed = (x, digits = 1) => Number(x).toFixed(digits);
export const percent = (fraction, digits = 0) => `${(fraction * 100).toFixed(digits)}%`;
export const html = (strings, ...values) => strings.reduce((out, s, i) => out + s + (i < values.length ? values[i] : ""), "");

const KIND_LABELS = {
  budget: "Budget",
  duration: "Duration",
  experience: "Experience",
  technology: "Technology",
  text: "Semantic text",
};
export const kindLabel = (kind) => KIND_LABELS[kind] ?? cap(kind);

const STATUS_LABELS = { pass: "Pass", warning: "Warning", fail: "Fail", missing: "Missing", review: "Review" };

export function status(value, text) {
  if (!value) return `<span class="muted">—</span>`;
  return `<span class="status st-${esc(value)}">${esc(text ?? STATUS_LABELS[value] ?? cap(value))}</span>`;
}

export function importanceBadge(importance) {
  return `<span class="badge imp-${esc(importance)}" title="Importance">${esc(cap(importance))}</span>`;
}

export function typeBadge(requirementType) {
  const title = requirementType === "hard" ? "Hard requirement: failing it applies a score multiplier" : "Soft requirement: failing it only loses its points";
  return `<span class="badge type-${esc(requirementType)}" title="${title}">${esc(cap(requirementType))}</span>`;
}

export function flexibilityBadge(flexibility) {
  if (!flexibility) return "";
  const title = flexibility === "strict" ? "Any deviation fails" : "Small deviations get a small, growing penalty";
  return `<span class="badge flex-${esc(flexibility)}" title="${title}">${esc(cap(flexibility))}</span>`;
}

export function criterionBadges(c) {
  return `<span class="badges">${importanceBadge(c.importance)}${typeBadge(c.requirement_type)}${flexibilityBadge(c.flexibility)}</span>`;
}

const LABEL_CLASSES = {
  "Strong compatibility": "lb-strong",
  "Mostly compatible with some concerns": "lb-mostly",
  "Requires review": "lb-review",
  "Hard requirement failed": "lb-failed",
};
export const compatibilityLabel = (label) => `<span class="label ${LABEL_CLASSES[label] ?? "lb-review"}">${esc(label)}</span>`;

export function scoreBar(value, max = 100, statusClass = "") {
  const width = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return `<span class="bar ${esc(statusClass)}" role="presentation"><span style="width:${width.toFixed(1)}%"></span></span>`;
}

export function overallScore(score) {
  return `<span class="score"><span class="score-num">${fixed(score)}</span>${scoreBar(score)}</span>`;
}

export function loading(message = "Loading…") {
  return `<div class="card state" role="status"><div class="spinner" aria-hidden="true"></div><p>${esc(message)}</p></div>`;
}

export function emptyState(title, text, actionsHtml = "") {
  return `<div class="card state"><h2>${esc(title)}</h2><p>${esc(text)}</p>${actionsHtml ? `<div class="actions">${actionsHtml}</div>` : ""}</div>`;
}

const ERROR_HINTS = {
  semantic_model_unavailable:
    "The local semantic model could not be loaded. Structured scoring is unaffected, but text criteria need the model. Check the server logs and network access for the first model download.",
  network_error: "Check that the FastAPI server is running and reachable.",
  not_found: "The project or vendor may have been deleted, or the demo storage was reset.",
};

export function errorState(error, { title = "Something went wrong", retry = true } = {}) {
  const hint = ERROR_HINTS[error?.code] ?? "";
  return `<div class="card state error" role="alert">
    <h2>${esc(title)}</h2>
    <p>${esc(error?.message ?? String(error))}</p>
    ${hint ? `<p class="small" style="margin-top:8px">${esc(hint)}</p>` : ""}
    ${error?.code ? `<code>${esc(error.code)}${error.status ? ` · HTTP ${esc(error.status)}` : ""}</code>` : ""}
    <div class="actions">
      ${retry ? `<button type="button" class="btn" data-action="retry">Retry</button>` : ""}
      <a class="btn" href="#/">Back to overview</a>
    </div>
  </div>`;
}
