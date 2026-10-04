// Entry point: hash router, global actions (Try Demo, retry, refresh) and error handling.

import { api } from "./api.js";
import { clearProjectBundles } from "./store.js";
import { errorState } from "./ui.js";
import { renderHome } from "./views/home.js";
import { renderProject } from "./views/project.js";
import { renderProjectForm } from "./views/project-form.js";
import { renderProjects } from "./views/projects.js";
import { renderVendor } from "./views/vendor.js";
import { renderVendorForm } from "./views/vendor-form.js";

const main = document.getElementById("app");

const routes = [
  { pattern: /^#?\/?$/, nav: "home", view: () => renderHome(main) },
  { pattern: /^#\/projects\/?$/, nav: "projects", view: () => renderProjects(main) },
  { pattern: /^#\/projects\/new\/?$/, nav: "projects", view: () => renderProjectForm(main) },
  { pattern: /^#\/projects\/(\d+)\/?$/, nav: "projects", view: (id) => renderProject(main, id) },
  { pattern: /^#\/projects\/(\d+)\/edit\/?$/, nav: "projects", view: (id) => renderProjectForm(main, id) },
  { pattern: /^#\/projects\/(\d+)\/vendors\/new\/?$/, nav: "projects", view: (pid) => renderVendorForm(main, pid) },
  { pattern: /^#\/projects\/(\d+)\/vendors\/(\d+)\/edit\/?$/, nav: "projects", view: (pid, vid) => renderVendorForm(main, pid, vid) },
  { pattern: /^#\/projects\/(\d+)\/vendors\/(\d+)\/?$/, nav: "projects", view: (pid, vid) => renderVendor(main, pid, vid) },
];

let renderToken = 0;

// Routes always start with "#/". Other hashes (e.g. "#scoring", "#app") are in-page anchors.
const isRouteHash = (hash) => hash === "" || hash.startsWith("#/");
const currentRoute = () => (isRouteHash(location.hash) && location.hash ? location.hash : "#/");

async function render({ refresh = false } = {}) {
  const token = ++renderToken;
  const hash = currentRoute();
  const route = routes.find((r) => r.pattern.test(hash));
  document.querySelectorAll("[data-nav]").forEach((a) => {
    if (a.dataset.nav === route?.nav) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });

  try {
    if (!route) {
      main.innerHTML = errorState({ code: "not_found", message: "This page does not exist." }, { title: "Page not found", retry: false });
      return;
    }
    const params = hash.match(route.pattern).slice(1);
    if (refresh && params.length) clearProjectBundles();
    await route.view(...params);
  } catch (error) {
    if (token !== renderToken) return; // a newer navigation already replaced this view
    console.error(error);
    main.innerHTML = errorState(error, { title: error.status === 404 ? "Not found" : "Could not load this page" });
  }
  if (token === renderToken) {
    document.title = titleFor(hash);
    if (location.hash && !isRouteHash(location.hash)) document.querySelector(location.hash)?.scrollIntoView();
  }
}

function titleFor(hash) {
  const heading = main.querySelector("h1")?.textContent?.trim();
  return heading && hash !== "#/" ? `${heading} · VendorMatch AI` : "VendorMatch AI — Software Vendor Evaluation";
}

async function tryDemo(button) {
  const buttons = document.querySelectorAll('[data-action="try-demo"]');
  buttons.forEach((b) => { b.disabled = true; b.dataset.label = b.textContent; b.textContent = "Loading demo…"; });
  try {
    const demo = await api.loadDemo();
    location.hash = `#/projects/${demo.project_id}`;
  } catch (error) {
    main.innerHTML = errorState(error, { title: "The demo could not be loaded" });
  } finally {
    buttons.forEach((b) => { b.disabled = false; b.textContent = b.dataset.label; });
  }
}

// In-page "click twice" confirmation. Browser confirm() dialogs are blocked silently in some
// browsers (they return false without showing anything), which made Delete do nothing.
const CONFIRM_WINDOW_MS = 4000;

function confirmByClickingTwice(button, prompt) {
  if (button.dataset.armed === "1") return true;
  button.dataset.armed = "1";
  button.dataset.label = button.textContent;
  button.textContent = prompt;
  button.classList.add("btn-danger");
  setTimeout(() => {
    if (!button.isConnected || button.dataset.armed !== "1") return;
    button.dataset.armed = "";
    button.textContent = button.dataset.label;
    button.classList.remove("btn-danger");
  }, CONFIRM_WINDOW_MS);
  return false;
}

async function deleteProject(button) {
  if (!confirmByClickingTwice(button, "Click again to delete the project")) return;
  button.disabled = true;
  try {
    await api.deleteProject(button.dataset.id);
    clearProjectBundles();
    location.hash = "#/projects";
  } catch (error) {
    main.innerHTML = errorState(error, { title: "The project could not be deleted" });
  }
}

async function deleteVendor(button) {
  if (!confirmByClickingTwice(button, "Click again to delete this offer")) return;
  button.disabled = true;
  const { project: projectId, id } = button.dataset;
  try {
    await api.deleteVendor(id);
    clearProjectBundles();
    location.hash = `#/projects/${projectId}`;
  } catch (error) {
    main.innerHTML = errorState(error, { title: "The offer could not be deleted" });
  }
}

document.addEventListener("click", (event) => {
  const action = event.target.closest("[data-action]");
  if (action) {
    const name = action.dataset.action;
    if (name === "try-demo") tryDemo(action);
    if (name === "retry") render();
    if (name === "refresh") render({ refresh: true });
    if (name === "delete-project") deleteProject(action);
    if (name === "delete-vendor") deleteVendor(action);
    return;
  }
  // Whole table rows are clickable; inner links keep working normally.
  const row = event.target.closest("tr[data-href]");
  if (row && !event.target.closest("a, button")) location.hash = row.dataset.href;
});

window.addEventListener("hashchange", () => {
  if (!isRouteHash(location.hash)) return; // let the browser scroll to the anchor
  render();
  window.scrollTo(0, 0);
});
render();
