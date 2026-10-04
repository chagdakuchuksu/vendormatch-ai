import { api } from "../api.js";
import { emptyState, esc } from "../ui.js";

const dateFormat = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

export function projectTable(projects) {
  const rows = projects
    .map(
      (p) => `
      <tr class="row-link" data-href="#/projects/${p.id}">
        <td data-label="Project"><a class="vendor-name" href="#/projects/${p.id}">${esc(p.name)}</a>
          ${p.is_demo ? ` <span class="badge kind">Fictional demo</span>` : ""}</td>
        <td data-label="Vendors" class="num">${p.vendor_count}</td>
        <td data-label="Criteria" class="num">${p.criteria_count}</td>
        <td data-label="Created">${esc(dateFormat.format(new Date(p.created_at)))}</td>
      </tr>`
    )
    .join("");
  return `<div class="card table-wrap"><table class="stackable">
    <thead><tr><th>Project</th><th class="num">Vendors</th><th class="num">Criteria</th><th>Created</th></tr></thead>
    <tbody>${rows}</tbody></table></div>`;
}

export async function renderProjects(main) {
  main.innerHTML = `<div class="section-head"><h1>Projects</h1><a class="btn btn-primary" href="#/projects/new">+ New project</a></div><div id="list"></div>`;
  const list = main.querySelector("#list");
  list.innerHTML = `<div class="card state"><p class="muted">Loading projects…</p></div>`;
  const projects = await api.listProjects();
  list.innerHTML = projects.length
    ? projectTable(projects)
    : emptyState(
        "No projects yet",
        "Create a project with your own requirements, or load the fictional demo to see a complete evaluation.",
        `<a class="btn btn-primary" href="#/projects/new">+ New project</a><button type="button" class="btn" data-action="try-demo">Try Demo</button>`
      );
}
