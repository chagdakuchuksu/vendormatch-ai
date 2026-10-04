import { api } from "../api.js";
import { esc, fixed } from "../ui.js";
import { projectTable } from "./projects.js";

export async function renderHome(main) {
  main.innerHTML = `
    <section class="intro">
      <div>
        <div class="eyebrow">AI-powered software vendor evaluation</div>
        <h1>Compare development proposals against your own requirements.</h1>
        <p class="lead">
          VendorMatch AI scores each vendor proposal against the budget, deadline, technologies and experience you
          define — and shows exactly why: weighted criteria, hard-requirement checks and quoted evidence.
          It supports your team's decision; it does not make it.
        </p>
        <div class="actions">
          <button type="button" class="btn btn-primary btn-lg" data-action="try-demo">Try Demo</button>
          <a class="btn btn-lg" href="#/projects/new">Create your own project</a>
          <a class="btn btn-lg btn-ghost" href="#scoring">How scoring works</a>
        </div>
        <p class="small muted" style="margin-top:12px">The demo loads a fictional e-commerce project with three fictional vendors. Or enter your own requirements and vendor offers. No sign-up.</p>
      </div>
      <div class="card card-pad" id="scoring">
        <h3>Scoring at a glance</h3>
        <div class="formula-mini">Overall = Base score × hard-failure multiplier</div>
        <div class="formula-mini">Base score = Σ (criterion weight × criterion score)</div>
        <dl class="kv" style="margin-top:14px" id="scoring-facts">
          <dt>Numbers &amp; tech</dt><dd>Deterministic rules — budget, duration, experience, technology lists</dd>
          <dt>Text</dt><dd>Local semantic similarity, shown with the quoted sentence as evidence</dd>
          <dt>Hard failures</dt><dd class="muted">Loading multipliers…</dd>
        </dl>
      </div>
    </section>

    <section class="section steps">
      <div class="card step">
        <div class="step-num">STEP 1</div>
        <h3>Define requirements</h3>
        <p>Budget, deadline, technologies and experience — each with an importance, Hard or Soft, and Strict or Flexible.</p>
      </div>
      <div class="card step">
        <div class="step-num">STEP 2</div>
        <h3>Add vendor proposals</h3>
        <p>Price, timeline, technology stack, company experience and the proposal text itself.</p>
      </div>
      <div class="card step">
        <div class="step-num">STEP 3</div>
        <h3>Review the analysis</h3>
        <p>Compare vendors side by side and open any vendor to see every point earned or lost, with evidence.</p>
      </div>
    </section>

    <section class="section">
      <div class="section-head"><h2>Recent projects</h2><a href="#/projects" class="small">All projects →</a></div>
      <div id="recent">${"<div class=\"card state\"><p class=\"muted\">Loading projects…</p></div>"}</div>
    </section>`;

  const [model, projects] = await Promise.allSettled([api.scoringModel(), api.listProjects()]);

  const facts = main.querySelector("#scoring-facts dd:last-child");
  if (model.status === "fulfilled") {
    const f = model.value.hard_fail_factors;
    facts.classList.remove("muted");
    facts.textContent = `Score × ${fixed(f.critical, 1)} (critical), × ${fixed(f.high, 1)} (high), × ${fixed(f.medium, 1)} (medium), × ${fixed(f.low, 1)} (low) per failed hard requirement — vendors are never hidden`;
  } else {
    facts.textContent = "Could not load the scoring model.";
  }

  const recent = main.querySelector("#recent");
  if (projects.status === "rejected") {
    recent.innerHTML = `<div class="card state error"><p>${esc(projects.reason.message)}</p></div>`;
  } else if (projects.value.length === 0) {
    recent.innerHTML = `<div class="card state"><p>No projects yet. Use <strong>Try Demo</strong> to load the fictional example, or <a href="#/projects/new">create your own project</a>.</p></div>`;
  } else {
    recent.innerHTML = projectTable(projects.value.slice(0, 5));
  }
}
