// Vendor analysis screen: score formula, concerns and a full per-criterion breakdown.

import { ApiError } from "../api.js";
import { loadProjectBundle } from "../store.js";
import {
  compatibilityLabel,
  criterionBadges,
  esc,
  fixed,
  kindLabel,
  loading,
  percent,
  scoreBar,
  status,
} from "../ui.js";

const STRENGTH_LABELS = { strong: "Strong match", partial: "Partial match", none: "No match" };

export async function renderVendor(main, projectId, vendorId) {
  main.innerHTML = loading("Loading vendor analysis…");
  let bundle = await loadProjectBundle(projectId);
  const findResult = (b) => b.analysis.vendors.find((v) => String(v.vendor_id) === String(vendorId));
  if (!findResult(bundle)) bundle = await loadProjectBundle(projectId, { refresh: true }); // cached data may be stale
  const { project, vendors, analysis } = bundle;
  const result = findResult(bundle);
  if (!result) throw new ApiError(404, "not_found", `Vendor ${vendorId} is not part of this project.`);
  const proposal = vendors.find((v) => String(v.id) === String(vendorId));

  main.innerHTML = `
    <div class="crumbs"><a href="#/projects">Projects</a> / <a href="#/projects/${project.id}">${esc(project.name)}</a> / ${esc(result.vendor_name)}</div>
    ${vendorTabs(project.id, analysis.vendors, vendorId)}
    <section class="section">
      <div class="vendor-head">
        <div>
          <h1>${esc(result.vendor_name)}</h1>
          <div style="margin-top:8px">${compatibilityLabel(result.compatibility_label)}</div>
        </div>
        <div class="actions" style="margin-top:0">
          <a class="btn" href="#/projects/${project.id}">← Back to comparison</a>
          <a class="btn" href="#/projects/${project.id}/vendors/${result.vendor_id}/edit">Edit offer</a>
          <button type="button" class="btn btn-ghost" data-action="delete-vendor" data-project="${project.id}" data-id="${result.vendor_id}" data-name="${esc(result.vendor_name)}">Delete</button>
        </div>
      </div>
      <p class="vendor-summary">${esc(result.summary)}</p>
    </section>
    ${formula(result)}
    ${concerns(result)}
    <section class="section">
      <div class="section-head">
        <h2>Criterion breakdown</h2>
        <p>${result.criteria.length} criteria · points earned out of each criterion's maximum</p>
      </div>
      <div class="card">${result.criteria.map(criterionBlock).join("")}</div>
    </section>
    ${proposal ? proposalSection(proposal, project.currency) : ""}
    <section class="section"><div class="note"><strong>Decision support</strong><span>${esc(analysis.disclaimer)}</span></div></section>`;
}

function vendorTabs(projectId, vendors, currentId) {
  const tabs = vendors
    .map(
      (v) => `<a class="vendor-tab" href="#/projects/${projectId}/vendors/${v.vendor_id}"
        ${String(v.vendor_id) === String(currentId) ? 'aria-current="page"' : ""}>${esc(v.vendor_name)}
        <span class="mono">${fixed(v.overall_score)}</span></a>`
    )
    .join("");
  return `<nav class="vendor-tabs" aria-label="Vendors in this project">${tabs}</nav>`;
}

function formula(r) {
  const failed = r.criteria.filter((c) => c.hard_failure);
  const multiplierNote = failed.length
    ? failed.map((c) => `${esc(c.name)} failed (${esc(c.importance)}) ×${fixed(c.penalty_factor, 2)}`).join("<br>")
    : "No hard requirement failed";
  return `
    <section class="section">
      <div class="section-head"><h2>How the score is calculated</h2></div>
      <div class="card card-pad">
        <div class="formula" role="group" aria-label="Base score times hard-failure multiplier equals overall score">
          <div class="f-box">
            <div class="f-label">Base score</div>
            <div class="f-value">${fixed(r.base_score)}</div>
            <div class="f-note">Sum of points earned on all ${r.criteria.length} weighted criteria (max 100)</div>
          </div>
          <div class="f-op" aria-hidden="true">×</div>
          <div class="f-box ${failed.length ? "penalized" : ""}">
            <div class="f-label">Hard-failure multiplier</div>
            <div class="f-value">${fixed(r.hard_penalty_factor, 2)}</div>
            <div class="f-note">${multiplierNote}</div>
          </div>
          <div class="f-op" aria-hidden="true">=</div>
          <div class="f-box result">
            <div class="f-label">Overall score</div>
            <div class="f-value">${fixed(r.overall_score)}</div>
            <div class="f-note">${r.penalty_points > 0 ? `${fixed(r.penalty_points)} points removed by the multiplier` : "Equal to the base score"}</div>
          </div>
        </div>
        <p class="formula-caption">${esc(r.score_explanation)}</p>
      </div>
    </section>`;
}

function concerns(r) {
  const counts = r.counts;
  const items = r.major_concerns.length
    ? `<ul class="concerns">${r.major_concerns.map((c) => `<li>${esc(c)}</li>`).join("")}</ul>`
    : `<p class="muted small">No concerns: every criterion is fully met.</p>`;
  return `
    <section class="section">
      <div class="card card-pad">
        <div class="section-head" style="margin-bottom:8px"><h3>Concerns</h3>
          <p>Hard: ${counts.hard_passed} met · ${counts.hard_warning} partial · ${counts.hard_failed} failed
          &nbsp;|&nbsp; Soft: ${counts.soft_passed} met · ${counts.soft_warning} partial · ${counts.soft_failed} not met</p></div>
        ${items}
      </div>
    </section>`;
}

function criterionBlock(c) {
  const lost = c.points_lost;
  return `
    <article class="crit" aria-label="${esc(c.name)}">
      <div class="crit-head">
        <div>
          <div class="crit-title"><h3>${esc(c.name)}</h3>${status(c.status)}<span class="badge kind">${esc(kindLabel(c.kind))}</span></div>
          <div style="margin-top:6px">${criterionBadges(c)}</div>
        </div>
        <div class="crit-points">
          <div class="pts">${fixed(c.contribution, 2)} / ${fixed(c.max_points, 2)} pts</div>
          <div class="lost ${lost < 0.005 ? "zero" : ""}">${lost < 0.005 ? "no points lost" : `−${fixed(lost, 2)} points`}</div>
        </div>
      </div>
      ${scoreBar(c.contribution, c.max_points, c.status)}
      <dl class="crit-grid">
        <div><dt>Requirement</dt><dd>${esc(c.required_value)}</dd></div>
        <div><dt>Vendor</dt><dd>${esc(c.vendor_value)}</dd></div>
        <div><dt>Criterion score</dt><dd class="mono">${fixed(c.score, 2)}</dd></div>
        <div><dt>Weight</dt><dd>${percent(c.normalized_weight)}</dd></div>
      </dl>
      ${c.evidence ? evidenceBlock(c.evidence) : ""}
      <p class="explain">${esc(c.explanation)}</p>
      ${c.hard_failure ? `<p class="explain" style="color:var(--fail)"><strong>Hard requirement failed:</strong> the overall score is multiplied by ${fixed(c.penalty_factor, 2)}.</p>` : ""}
    </article>`;
}

function evidenceBlock(e) {
  const pos = (x) => `${(Math.max(0, Math.min(1, x)) * 100).toFixed(1)}%`;
  return `
    <div class="evidence">
      <div class="evidence-title">Semantic evidence · supporting signal, not a decision</div>
      <blockquote>${esc(e.matched_text)}</blockquote>
      <div class="src">Source: ${esc(e.source)} · compared with the requirement “${esc(e.requirement_text)}”</div>
      <div class="sim-scale" style="--lo:${pos(e.lower_threshold)};--hi:${pos(e.upper_threshold)}"
           role="img" aria-label="Similarity ${fixed(e.similarity, 2)} on a 0 to 1 scale">
        <div class="sim-track"></div>
        <div class="sim-tick" style="left:${pos(e.lower_threshold)}"></div>
        <div class="sim-tick" style="left:${pos(e.upper_threshold)}"></div>
        <div class="sim-dot" style="left:${pos(e.similarity)}"></div>
      </div>
      <div class="sim-legend"><span>0 · no match ≤ ${fixed(e.lower_threshold, 2)}</span><span>partial</span><span>strong ≥ ${fixed(e.upper_threshold, 2)} · 1</span></div>
      <dl class="crit-grid" style="margin-top:10px">
        <div><dt>Cosine similarity</dt><dd class="mono">${fixed(e.similarity, 2)}</dd></div>
        <div><dt>Match level</dt><dd>${esc(STRENGTH_LABELS[e.strength] ?? e.strength)}</dd></div>
        <div><dt>Normalized score</dt><dd class="mono">${fixed(e.normalized_score, 2)}</dd></div>
        <div><dt>Model</dt><dd>local MiniLM</dd></div>
      </dl>
      <p class="small muted" style="margin-top:8px">Similarity is measured sentence by sentence with a small local language model.
        The thresholds are provisional, and the model can miss nuance such as negation — read the quoted sentence before relying on it.</p>
    </div>`;
}

function proposalSection(v, currency) {
  const money = v.proposed_budget != null
    ? new Intl.NumberFormat("en-IE", { style: "currency", currency, maximumFractionDigits: 0 }).format(v.proposed_budget)
    : "not stated";
  return `
    <section class="section">
      <div class="section-head"><h2>Submitted proposal</h2><p>As stored — the input the analysis is based on</p></div>
      <div class="card card-pad proposal">
        <dl class="kv">
          <dt>Price</dt><dd>${esc(money)}</dd>
          <dt>Duration</dt><dd>${v.proposed_duration != null ? `${esc(fixed(v.proposed_duration, 0))} ${esc(v.duration_unit)}` : "not stated"}</dd>
          <dt>Experience</dt><dd>${v.years_experience != null ? `${esc(fixed(v.years_experience, 0))} years` : "not stated"}</dd>
          <dt>Technologies</dt><dd><span class="chips" style="margin:0">${v.technologies.map((t) => `<span class="chip">${esc(t)}</span>`).join("") || "—"}</span></dd>
        </dl>
        ${v.proposal_text ? `<h3 style="margin-top:16px">Proposal text</h3><p style="margin-top:6px">${esc(v.proposal_text)}</p>` : ""}
        ${v.previous_projects.length ? `<h3 style="margin-top:16px">Previous projects</h3><ul>${v.previous_projects.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}
      </div>
    </section>`;
}
