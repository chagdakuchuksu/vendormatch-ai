// Add / edit a vendor offer.

import { api } from "../api.js";
import { PUBLIC_NOTE, compact, errorList, field, readNumber, segmented, splitList } from "../forms.js";
import { clearProjectBundles } from "../store.js";
import { esc, loading } from "../ui.js";

const UNITS = [["months", "Months"], ["weeks", "Weeks"]];

export async function renderVendorForm(main, projectId, vendorId = null) {
  main.innerHTML = loading("Loading…");
  const [project, vendor] = await Promise.all([api.getProject(projectId), vendorId ? api.getVendor(vendorId) : null]);
  const currency = project.currency;

  main.innerHTML = `
    <div class="crumbs"><a href="#/projects">Projects</a> / <a href="#/projects/${project.id}">${esc(project.name)}</a> /
      ${vendor ? `${esc(vendor.name)} / Edit offer` : "New vendor offer"}</div>
    <div class="section-head"><h1>${vendor ? "Edit vendor offer" : "Add vendor offer"}</h1></div>
    <p class="muted small">${esc(PUBLIC_NOTE)}</p>
    <form class="form" novalidate>
      <div id="form-errors"></div>
      <section class="card card-pad form-section">
        <h2>Vendor</h2>
        ${field("Vendor name *", `<input name="name" required maxlength="120" value="${esc(vendor?.name ?? "")}" placeholder="e.g. Acme Software">`)}
        <div class="form-row">
          ${field(`Price (${esc(currency)})`, `<input name="proposed_budget" type="number" min="1" step="any" value="${esc(vendor?.proposed_budget ?? "")}" placeholder="e.g. 48000">`)}
          ${field("Years in business", `<input name="years_experience" type="number" min="0" step="0.5" value="${esc(vendor?.years_experience ?? "")}" placeholder="e.g. 7">`)}
        </div>
        <div class="form-row">
          ${field("Proposed duration", `<input name="proposed_duration" type="number" min="0.1" step="any" value="${esc(vendor?.proposed_duration ?? "")}" placeholder="e.g. 5">`)}
          <div class="field"><span class="field-label">Unit</span>${segmented("unit", UNITS, vendor?.duration_unit ?? project.duration_unit)}</div>
        </div>
      </section>
      <section class="card card-pad form-section">
        <h2>Proposal</h2>
        ${field("Proposal text", `<textarea name="proposal_text" rows="7" maxlength="10000" placeholder="Paste or summarize the vendor's proposal. Each sentence is compared with your text requirements.">${esc(vendor?.proposal_text ?? "")}</textarea>`)}
        ${field("Previous projects", `<textarea name="previous_projects" rows="4" placeholder="One project per line">${esc((vendor?.previous_projects ?? []).join("\n"))}</textarea>`, "One per line. Also used as evidence for text requirements.")}
      </section>
      <div class="form-actions">
        <a class="btn" href="#/projects/${project.id}${vendor ? `/vendors/${vendor.id}` : ""}">Cancel</a>
        <button type="submit" class="btn btn-primary">${vendor ? "Save changes" : "Add offer"}</button>
      </div>
    </form>`;

  const form = main.querySelector("form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const errors = form.querySelector("#form-errors");
    const value = (name) => form.querySelector(`[name="${name}"]`).value.trim();
    const numbers = ["proposed_budget", "proposed_duration", "years_experience"].map((n) => readNumber(form.querySelector(`[name="${n}"]`)));
    if (!value("name")) {
      errors.innerHTML = errorList({ message: "Please enter the vendor name." });
      return;
    }
    if (numbers.some(Number.isNaN)) {
      errors.innerHTML = errorList({ message: "Price, duration and years must be numbers." });
      return;
    }
    const [proposed_budget, proposed_duration, years_experience] = numbers;
    const payload = compact({
      name: value("name"),
      proposed_budget,
      proposed_duration,
      duration_unit: form.querySelector('[data-k="unit"] input:checked')?.value ?? "months",
      years_experience,
      // Technologies are no longer entered in the form; keep any existing ones (e.g. demo vendors).
      technologies: vendor?.technologies ?? [],
      proposal_text: value("proposal_text"),
      previous_projects: splitList(form.querySelector('[name="previous_projects"]').value, /\r?\n/),
    });

    const submit = form.querySelector('[type="submit"]');
    submit.disabled = true;
    submit.textContent = "Saving…";
    try {
      const saved = vendor ? await api.updateVendor(vendor.id, payload) : await api.createVendor(project.id, payload);
      clearProjectBundles();
      location.hash = `#/projects/${project.id}/vendors/${saved.id}`;
    } catch (error) {
      errors.innerHTML = errorList(error);
      errors.scrollIntoView({ block: "center" });
      submit.disabled = false;
      submit.textContent = vendor ? "Save changes" : "Add offer";
    }
  });
}
