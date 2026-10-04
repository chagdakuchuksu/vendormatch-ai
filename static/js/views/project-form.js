// Create / edit a project: budget, deadline, experience and free-text requirements.
// Users set an importance (and optionally a manual weight) per requirement; everything else uses fixed rules.
// Validation, weights and scoring happen on the server.

import { api } from "../api.js";
import { PUBLIC_NOTE, WEIGHT_HINT, compact, errorList, field, importanceControl, readImportance, readNumber, readWeight, segmented } from "../forms.js";
import { clearProjectBundles } from "../store.js";
import { esc, loading } from "../ui.js";

const CURRENCIES = [["EUR", "EUR €"], ["USD", "USD $"], ["GBP", "GBP £"], ["CHF", "CHF"]];
const UNITS = [["months", "Months"], ["weeks", "Weeks"]];

// Fixed rules per kind (not shown in the form). Every penalty is graded and scaled by the
// requirement's weight; nothing drops straight to zero for a small miss:
// - budget: quadratic curve, 25% tolerance (5% over -> 0.96, 10% -> 0.84, 20% -> 0.36)
// - deadline and experience: linear curve, 50% tolerance (1 month late on 12 -> 0.83, 3 -> 0.50, 6 -> 0)
// - text: semantic similarity
const DEFAULTS = {
  budget: { importance: "high", requirement_type: "soft", flexibility: "flexible" },
  duration: { importance: "critical", requirement_type: "soft", flexibility: "flexible", tolerance: 0.5, curve: "linear" },
  experience: { importance: "medium", requirement_type: "soft", flexibility: "flexible", tolerance: 0.5, curve: "linear" },
  text: { importance: "high", requirement_type: "soft" },
};
// Demo projects keep all of their original settings when edited, so their scores never change silently.
const DEMO_KEPT_FIELDS = ["id", "source", "requirement_type", "flexibility", "tolerance", "curve", "weight", "description"];

export async function renderProjectForm(main, projectId = null) {
  let project = null;
  if (projectId) {
    main.innerHTML = loading("Loading project…");
    project = await api.getProject(projectId);
  }
  const first = (kind) => (project?.criteria ?? []).find((c) => c.kind === kind);
  const budget = first("budget");
  const duration = first("duration");
  const experience = first("experience");
  const texts = (project?.criteria ?? []).filter((c) => c.kind === "text");
  const keptTech = (project?.criteria ?? []).filter((c) => c.kind === "technology").length;

  main.innerHTML = `
    <div class="crumbs"><a href="#/projects">Projects</a> / ${project ? `<a href="#/projects/${project.id}">${esc(project.name)}</a> / Edit` : "New project"}</div>
    <div class="section-head"><h1>${project ? "Edit project requirements" : "New project"}</h1></div>
    <p class="muted small">${esc(PUBLIC_NOTE)}</p>
    <form class="form" novalidate>
      <div id="form-errors"></div>

      <section class="card card-pad form-section">
        <h2>Project</h2>
        ${field("Project name *", `<input name="project_name" required maxlength="120" value="${esc(project?.name ?? "")}" placeholder="e.g. Customer portal rebuild">`)}
        ${field("Description", `<textarea name="description" rows="3" maxlength="5000" placeholder="What should be built, for whom, and any context vendors need.">${esc(project?.description ?? "")}</textarea>`)}
      </section>

      <section class="card card-pad form-section" data-criterion="budget">
        <h2>Budget</h2>
        <div class="form-row">
          ${field("Maximum budget", `<input name="budget" type="number" min="1" step="any" value="${esc(project?.budget ?? "")}" placeholder="50000">`, "Small overruns cost a few points, larger ones progressively more; 25% over or more earns 0. Leave empty to skip.")}
          <div class="field"><span class="field-label">Currency</span>${segmented("currency", CURRENCIES, project?.currency ?? "EUR")}</div>
        </div>
        ${importanceControl((budget ?? DEFAULTS.budget).importance, budget?.weight)}
      </section>

      <section class="card card-pad form-section" data-criterion="duration">
        <h2>Deadline</h2>
        <div class="form-row">
          ${field("Maximum duration", `<input name="max_duration" type="number" min="0.1" step="any" value="${esc(project?.max_duration ?? "")}" placeholder="6">`, "Each month (or week) late costs the same share of this requirement's points; 50% late or more earns 0. Leave empty to skip.")}
          <div class="field"><span class="field-label">Unit</span>${segmented("unit", UNITS, project?.duration_unit ?? "months")}</div>
        </div>
        ${importanceControl((duration ?? DEFAULTS.duration).importance, duration?.weight)}
      </section>

      <section class="card card-pad form-section" data-criterion="experience">
        <h2>Company experience</h2>
        ${field("Minimum years in business", `<input name="min_years" type="number" min="0.5" step="0.5" value="${esc(experience?.min_value ?? "")}" placeholder="e.g. 5">`, "Each missing year costs the same share of this requirement's points; half the minimum or less earns 0. Leave empty to skip.")}
        ${importanceControl((experience ?? DEFAULTS.experience).importance, experience?.weight)}
      </section>

      <section class="card card-pad form-section">
        <div class="section-head"><h2>Other requirements</h2>
          <button type="button" class="btn" data-add="text">+ Add requirement</button></div>
        <p class="field-hint">Describe what you need in plain words. Each vendor's proposal is searched for the most similar sentence, which is shown as evidence.</p>
        <div data-list="text">${texts.map(textRow).join("")}</div>
      </section>

      <div class="form-actions">
        <a class="btn" href="${project ? `#/projects/${project.id}` : "#/projects"}">Cancel</a>
        <button type="submit" class="btn btn-primary">${project ? "Save changes" : "Create project"}</button>
      </div>
      <p class="field-hint">${esc(WEIGHT_HINT)}
        ${keptTech ? `This project also has ${keptTech} technology requirement(s), which stay unchanged.` : ""}</p>
    </form>`;

  const form = main.querySelector("form");
  if (!project) form.querySelector('[data-list="text"]').insertAdjacentHTML("beforeend", textRow({}));

  form.addEventListener("click", (event) => {
    if (event.target.closest("[data-add]")) {
      const list = form.querySelector('[data-list="text"]');
      list.insertAdjacentHTML("beforeend", textRow({}));
      list.querySelector(".repeat-row:last-child input")?.focus();
    }
    const remove = event.target.closest("[data-remove]");
    if (remove) remove.closest(".repeat-row").remove();
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errors = form.querySelector("#form-errors");
    let payload;
    try {
      payload = collect(form, project);
    } catch (message) {
      errors.innerHTML = errorList({ message });
      errors.scrollIntoView({ block: "center" });
      return;
    }
    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Saving…";
    try {
      const saved = project ? await api.updateProject(project.id, payload) : await api.createProject(payload);
      clearProjectBundles();
      location.hash = `#/projects/${saved.id}`;
    } catch (error) {
      errors.innerHTML = errorList(error);
      errors.scrollIntoView({ block: "center" });
      submit.disabled = false;
      submit.textContent = project ? "Save changes" : "Create project";
    }
  });
}

function textRow(c) {
  return `<div class="repeat-row" data-row="text" ${c.id ? `data-id="${esc(c.id)}"` : ""}>
    <div class="repeat-main">
      ${field("Name", `<input name="text_name" maxlength="100" value="${esc(c.name ?? "")}" placeholder="e.g. E-commerce experience">`)}
      <button type="button" class="btn btn-ghost" data-remove aria-label="Remove requirement">Remove</button>
    </div>
    ${field("Requirement", `<input name="text_description" maxlength="1000" value="${esc(c.description ?? "")}" placeholder="e.g. Previous e-commerce experience">`)}
    ${importanceControl((c.id ? c : DEFAULTS.text).importance, c.weight)}
  </div>`;
}

/** Hidden settings: the documented rules for the kind; demo criteria keep their original settings. */
function baseSettings(kind, existing, isDemo) {
  if (existing && isDemo) {
    return Object.fromEntries(DEMO_KEPT_FIELDS.filter((k) => existing[k] != null).map((k) => [k, existing[k]]));
  }
  const keep = existing ? compact({ id: existing.id, source: existing.source, description: existing.description }) : {};
  return { ...DEFAULTS[kind], ...keep };
}

/** Turn the form into a ProjectCreate / ProjectUpdate payload. Throws a message for obvious gaps. */
function collect(form, project) {
  const value = (name) => form.querySelector(`[name="${name}"]`)?.value.trim() ?? "";
  const existing = (kind) => project?.criteria.find((c) => c.kind === kind);
  const name = value("project_name");
  if (!name) throw "Please enter a project name.";

  const budget = readNumber(form.querySelector('[name="budget"]'));
  const maxDuration = readNumber(form.querySelector('[name="max_duration"]'));
  const minYears = readNumber(form.querySelector('[name="min_years"]'));
  if ([budget, maxDuration, minYears].some(Number.isNaN)) throw "Budget, duration and years must be numbers.";

  const criteria = [];
  const add = (kind, fields, scope) =>
    criteria.push(compact({ ...baseSettings(kind, existing(kind), project?.is_demo), ...fields, kind, importance: readImportance(scope), weight: readWeight(scope) }));

  if (budget != null) add("budget", { name: existing("budget")?.name ?? "Budget" }, form.querySelector('[data-criterion="budget"]'));
  if (maxDuration != null) add("duration", { name: existing("duration")?.name ?? "Duration" }, form.querySelector('[data-criterion="duration"]'));
  if (minYears != null) {
    add("experience", { name: existing("experience")?.name ?? "Company experience", min_value: minYears }, form.querySelector('[data-criterion="experience"]'));
  }

  for (const row of form.querySelectorAll('[data-row="text"]')) {
    const description = row.querySelector('[name="text_description"]').value.trim();
    const label = row.querySelector('[name="text_name"]').value.trim();
    if (!description && !label) continue;
    if (!description) throw `Please describe the requirement "${label}".`;
    const original = project?.criteria.find((c) => c.id === row.dataset.id);
    criteria.push(compact({
      ...baseSettings("text", original, project?.is_demo),
      kind: "text",
      name: label || description.slice(0, 100),
      description,
      importance: readImportance(row),
      weight: readWeight(row),
    }));
  }

  // Technology requirements are no longer edited in the form; existing ones (e.g. the demo's) are kept as they are.
  const technologies = (project?.criteria ?? []).filter((c) => c.kind === "technology");
  const afterLimits = criteria.filter((c) => c.kind === "budget" || c.kind === "duration").length;
  criteria.splice(afterLimits, 0, ...technologies);

  if (!criteria.length) throw "Add at least one requirement: a budget, a deadline, experience or a written requirement.";

  return compact({
    name,
    description: value("description"),
    budget,
    currency: form.querySelector('[data-k="currency"] input:checked')?.value ?? "EUR",
    max_duration: maxDuration,
    duration_unit: form.querySelector('[data-k="unit"] input:checked')?.value ?? "months",
    required_technologies: project?.required_technologies ?? [],
    criteria,
  });
}
