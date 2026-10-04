// Project screen: overview, requirements, vendor comparison and points-by-criterion matrix.
// Everything shown comes from /comparison and /analysis; no scores are computed here.

import { loadProjectBundle } from "../store.js";
import {
  compatibilityLabel,
  criterionBadges,
  emptyState,
  esc,
  fixed,
  kindLabel,
  loading,
  overallScore,
  percent,
  scoreBar,
  status,
} from "../ui.js";

const money = (amount, currency) =>
  new Intl.NumberFormat("en-IE", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);

export async function renderProject(main, projectId, { refresh = false } = {}) {
  main.innerHTML = loading("Analyzing vendor proposals… The first analysis loads the local language model and can take a few seconds.");
  const { project, vendors, comparison } = await loadProjectBundle(projectId, { refresh });

  main.innerHTML = `
    ${overview(project, comparison, vendors)}
    ${requirements(project, comparison)}
    ${comparisonSection(project, comparison)}
    ${matrixSection(comparison)}
    <section class="section">
      <div class="note"><strong>Ordering</strong><span>${esc(comparison.ordering_note)}</span></div>
      <div class="note"><strong>Decision support</strong><span>${esc(comparison.disclaimer)}</span></div>
      <p class="small muted" style="margin-top:10px">Scoring model v${esc(comparison.scoring_version)} · analysis generated
        ${esc(new Date(comparison.generated_at).toLocaleString())} from the current stored data.
        <button type="button" class="btn" data-action="refresh" style="height:28px;margin-left:6px">Refresh analysis</button></p>
    </section>`;
}

function overview(project, comparison, vendors) {
  const budget = project.criteria.find((c) => c.kind === "budget");
  const duration = project.criteria.find((c) => c.kind === "duration");
  const describe = (c) => (c ? [c.requirement_type, c.flexibility].filter(Boolean).join(" · ") : "not scored");
  return `
    <div class="crumbs"><a href="#/projects">Projects</a> / ${esc(project.name)}</div>
    <div class="vendor-head">
      <div>
        <h1>${esc(project.name)}</h1>
        ${project.is_demo ? `<div class="badges" style="margin-top:8px"><span class="badge kind">Fictional demo data</span></div>` : ""}
      </div>
      <div class="actions" style="margin-top:0">
        <a class="btn btn-primary" href="#/projects/${project.id}/vendors/new">+ Add vendor offer</a>
        <a class="btn" href="#/projects/${project.id}/edit">Edit requirements</a>
        <button type="button" class="btn btn-ghost" data-action="delete-project" data-id="${project.id}" data-name="${esc(project.name)}">Delete</button>
      </div>
    </div>
    ${project.description ? `<p class="vendor-summary">${esc(project.description)}</p>` : ""}
    <div class="card stats section ${project.required_technologies.length ? "" : "stats-4"}" style="margin-top:18px">
      <div class="stat"><div class="stat-label">Budget</div>
        <div class="stat-value">${project.budget ? esc(money(project.budget, project.currency)) : "—"}</div>
        <div class="stat-note">${esc(describe(budget))}</div></div>
      <div class="stat"><div class="stat-label">Max duration</div>
        <div class="stat-value">${project.max_duration ? `${esc(fixed(project.max_duration, 0))} ${esc(project.duration_unit)}` : "—"}</div>
        <div class="stat-note">${esc(describe(duration))}</div></div>
      ${project.required_technologies.length ? `<div class="stat"><div class="stat-label">Required technologies</div>
        <div class="chips">${project.required_technologies.map((t) => `<span class="chip">${esc(t)}</span>`).join("")}</div></div>` : ""}
      <div class="stat"><div class="stat-label">Criteria</div>
        <div class="stat-value">${comparison.criteria.length}</div>
        <div class="stat-note">${project.criteria.filter((c) => c.requirement_type === "hard").length} hard · ${project.criteria.filter((c) => c.requirement_type === "soft").length} soft</div></div>
      <div class="stat"><div class="stat-label">Vendors</div>
        <div class="stat-value">${vendors.length}</div>
        <div class="stat-note">all shown, none hidden</div></div>
    </div>`;
}

function requirements(project, comparison) {
  const descriptions = Object.fromEntries(project.criteria.map((c) => [c.id, c.description]));
  const rows = comparison.criteria
    .map(
      (c) => `
      <tr>
        <td data-label="Requirement"><div class="req-name">${esc(c.name)}</div>
          ${descriptions[c.id] ? `<div class="req-desc">${esc(descriptions[c.id])}</div>` : ""}</td>
        <td data-label="Type"><span class="badge kind">${esc(kindLabel(c.kind))}</span></td>
        <td data-label="Target">${esc(c.required_value)}</td>
        <td data-label="Rules">${criterionBadges(c)}</td>
        <td data-label="Weight" class="num"><span class="score" style="min-width:120px;justify-content:flex-end">
          <span>${percent(c.normalized_weight)}</span>${scoreBar(c.normalized_weight, 0.25)}</span>
          <span class="sub">${fixed(c.max_points)} of 100 pts</span></td>
      </tr>`
    )
    .join("");
  return `
    <section class="section">
      <div class="section-head">
        <h2>Requirements</h2>
        <p>Importance sets the default weight. <strong>Hard</strong> failures multiply the score down; <strong>Soft</strong> gaps only lose their own points. <strong>Flexible</strong> numbers tolerate small deviations.</p>
      </div>
      <div class="card table-wrap"><table class="stackable">
        <thead><tr><th>Requirement</th><th>Type</th><th>Target</th><th>Importance · Hard/Soft · Strict/Flexible</th><th class="num">Weight</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </section>`;
}

function hardCell(r) {
  if (r.hard_requirements_total === 0) return `<span class="muted">none defined</span>`;
  if (r.hard_requirements_failed === 0) return `${status("pass", `${r.hard_requirements_passed}/${r.hard_requirements_total} met`)}`;
  return `${status("fail", `${r.hard_requirements_failed} of ${r.hard_requirements_total} failed`)}
    <span class="sub">${esc(r.failed_hard_requirements.join(", "))}</span>`;
}

function concernsCell(r) {
  if (!r.major_concerns.length) return `<span class="muted">None</span>`;
  const shown = r.major_concerns.slice(0, 2).map((c) => `<li>${esc(c)}</li>`).join("");
  const more = r.major_concerns.length > 2 ? `<li class="muted">+${r.major_concerns.length - 2} more in the full analysis</li>` : "";
  return `<ul class="concerns">${shown}${more}</ul>`;
}

function comparisonSection(project, comparison) {
  if (!comparison.rows.length) {
    return `<section class="section"><div class="section-head"><h2>Vendor comparison</h2></div>
      ${emptyState("No vendor offers yet", "Add the offers you received to see the comparison and the analysis.",
        `<a class="btn btn-primary" href="#/projects/${project.id}/vendors/new">+ Add vendor offer</a>`)}</section>`;
  }
  const rows = comparison.rows
    .map(
      (r) => `
      <tr class="row-link" data-href="#/projects/${project.id}/vendors/${r.vendor_id}">
        <td data-label="Vendor"><a class="vendor-name" href="#/projects/${project.id}/vendors/${r.vendor_id}">${esc(r.vendor_name)}</a>
          <span class="sub">View full analysis →</span></td>
        <td data-label="Overall score">${overallScore(r.overall_score)}
          ${r.hard_penalty_factor < 1 ? `<span class="sub">base ${fixed(r.base_score)} × ${fixed(r.hard_penalty_factor, 2)}</span>` : ""}</td>
        <td data-label="Assessment">${compatibilityLabel(r.compatibility_label)}</td>
        <td data-label="Hard requirements">${hardCell(r)}</td>
        <td data-label="Budget"><strong>${esc(r.budget)}</strong> ${status(r.budget_status)}
          ${r.budget_summary ? `<span class="sub">${esc(r.budget_summary)}</span>` : ""}</td>
        <td data-label="Duration"><strong>${esc(r.duration)}</strong> ${status(r.duration_status)}
          ${r.duration_summary ? `<span class="sub">${esc(r.duration_summary)}</span>` : ""}</td>
        <td data-label="Technology"><strong>${esc(r.technology)}</strong> ${status(r.technology_status)}
          ${r.missing_technologies.length ? `<span class="sub">Missing: ${esc(r.missing_technologies.join(", "))}</span>` : ""}</td>
        <td data-label="Text evidence">${status(r.semantic_status)}<span class="sub">${esc(r.semantic_summary)}</span></td>
        <td data-label="Major concerns">${concernsCell(r)}</td>
      </tr>`
    )
    .join("");
  return `
    <section class="section">
      <div class="section-head">
        <h2>Vendor comparison</h2>
        <p>Open a vendor to see every point earned or lost.</p>
      </div>
      <div class="card table-wrap"><table class="stackable comparison">
        <thead><tr>
          <th>Vendor</th><th>Overall score</th><th>Assessment</th><th>Hard requirements</th>
          <th>Budget</th><th>Duration</th><th>Technology</th><th>Text evidence</th><th>Major concerns</th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </section>`;
}

function matrixSection(comparison) {
  if (!comparison.rows.length) return "";
  const head = comparison.rows.map((r) => `<th class="num">${esc(r.vendor_name)}</th>`).join("");
  const body = comparison.criteria
    .map((c) => {
      const cells = comparison.rows
        .map((r) => {
          const cell = r.cells[c.id];
          return `<td class="cell cell-${esc(cell.status)}" title="${esc(cell.summary)}">${fixed(cell.contribution, 2)}</td>`;
        })
        .join("");
      return `<tr><td><span class="req-name">${esc(c.name)}</span>${c.required_value !== c.name ? ` <span class="sub">${esc(c.required_value)}</span>` : ""}</td>
        <td class="num">${fixed(c.max_points)}</td>${cells}</tr>`;
    })
    .join("");
  const foot = (label, value) =>
    `<tr><td>${label}</td><td></td>${comparison.rows.map((r) => `<td>${value(r)}</td>`).join("")}</tr>`;
  return `
    <section class="section">
      <div class="section-head">
        <h2>Points by criterion</h2>
        <p>Points earned out of each criterion's maximum. Hover a cell for the reason.</p>
      </div>
      <div class="card table-wrap"><table class="matrix">
        <thead><tr><th>Criterion</th><th class="num">Max</th>${head}</tr></thead>
        <tbody>${body}</tbody>
        <tfoot>
          ${foot("Base score", (r) => fixed(r.base_score))}
          ${foot("Hard-failure multiplier", (r) => `× ${fixed(r.hard_penalty_factor, 2)}`)}
          ${foot("Overall score", (r) => fixed(r.overall_score))}
        </tfoot>
      </table></div>
    </section>`;
}
