// Shared form building blocks: segmented radio controls, importance picker, reading values, errors.

import { esc } from "./ui.js";

let uid = 0;
export const nextUid = () => ++uid;

export const IMPORTANCE = [["critical", "Critical"], ["high", "High"], ["medium", "Medium"], ["low", "Low"]];

export function segmented(key, options, value, id = nextUid()) {
  const items = options
    .map(([v, label]) => `<label><input type="radio" name="${key}-${id}" value="${esc(v)}" ${v === value ? "checked" : ""}><span>${esc(label)}</span></label>`)
    .join("");
  return `<div class="segmented" data-k="${key}" role="radiogroup">${items}</div>`;
}

export function field(label, control, hint = "") {
  return `<label class="field"><span class="field-label">${label}</span>${control}${hint ? `<span class="field-hint">${hint}</span>` : ""}</label>`;
}

/** Per-criterion settings users set themselves: importance and an optional manual weight. */
export function importanceControl(importance, weight = null) {
  return `<div class="rules">
    <div class="rule"><span class="rule-label">Importance</span>${segmented("importance", IMPORTANCE, importance)}</div>
    <div class="rule rule-weight"><span class="rule-label">Weight (optional)</span>
      <input type="number" data-k="weight" min="0" step="0.5" placeholder="auto" value="${esc(weight ?? "")}" aria-label="Weight (optional)"></div>
  </div>`;
}

export const WEIGHT_HINT =
  "Weight is optional. Leave it on \"auto\" and the importance decides (Critical 4, High 3, Medium 2, Low 1). " +
  "Or type your own number: weights are relative, so a requirement with weight 6 counts twice as much as one with 3. " +
  "The project page shows each requirement's resulting share of the 100 points.";

export function readImportance(scope) {
  return scope.querySelector('[data-k="importance"] input:checked')?.value ?? "medium";
}

/** Manual weight, or null for "auto" (importance decides). Throws a message for invalid input. */
export function readWeight(scope) {
  const weight = readNumber(scope.querySelector('input[data-k="weight"]'));
  if (weight != null && !(weight >= 0)) throw "Weight must be a number of 0 or more, or empty for auto.";
  return weight;
}

export function readNumber(input) {
  const raw = input?.value?.trim();
  if (raw === undefined || raw === "") return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : NaN;
}

/** Drop null / undefined / empty-string values (the API forbids unknown keys, not missing ones). */
export function compact(obj) {
  return Object.fromEntries(Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== ""));
}

export const splitList = (text, separator) =>
  text.split(separator).map((s) => s.trim()).filter(Boolean);

function prettyLocation(loc) {
  return loc
    .filter((part) => part !== "body")
    .map((part) => (typeof part === "number" ? `#${part + 1}` : String(part).replaceAll("_", " ")))
    .join(" › ");
}

export function errorList(error) {
  const details = error?.details ?? {};
  let items = [];
  if (Array.isArray(details.errors)) {
    items = details.errors.map((e) => (typeof e === "string" ? e : `${prettyLocation(e.loc ?? [])}: ${e.message}`));
  }
  return `<div class="form-errors" role="alert">
    <strong>${esc(error?.message ?? "The form could not be saved.")}</strong>
    ${items.length ? `<ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : ""}
  </div>`;
}

export const PUBLIC_NOTE =
  "Public demo: there are no accounts, anyone can see projects, and data resets when the server restarts. Do not enter confidential information.";
