import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { phase10Scenario, learner } from "../src/test/phase10Scenario";
import { citation, id } from "../src/test/scenario";

async function capture(page: Page, info: TestInfo, name: string, fixture = false) {
  await page.evaluate(() => document.fonts.ready);
  if (fixture) await page.evaluate(() => {
    if (document.getElementById("fixture-label")) return;
    const label = document.createElement("div");
    label.id = "fixture-label";
    label.textContent = "EXAMPLE DATA · Browser test fixture · Not learner results";
    label.style.cssText = "position:absolute;top:0;left:0;right:0;z-index:9999;padding:3px;text-align:center;font:9px sans-serif;background:#344a53;color:white;";
    document.body.append(label);
  });
  await mkdir("review", { recursive: true });
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1)).toBe(true);
  await page.screenshot({ path: `review/${info.project.name}-${name}.png`, fullPage: true });
}

test("Observatory skip, return visit and reduced motion", async ({ page }, info) => {
  await page.route(url => url.pathname.startsWith("/api/"), route => route.fulfill({ json: [] }));
  await page.goto("/?intro=1");
  await expect(page.getByRole("heading", { name: "See how ideas connect." })).toBeVisible();
  expect(await page.locator(".glass-prerequisite").evaluate(el => getComputedStyle(el).animationName)).toBe("none");
  await capture(page, info, "hero");
  await page.getByRole("button", { name: "Skip intro" }).click();
  await expect(page).toHaveURL(/\/workspace$/);
  await expect(page.getByRole("heading", { name: "Create a course" })).toBeVisible();
  await page.goto("/");
  await expect(page).toHaveURL(/\/workspace$/);
  await page.goto("/?intro=1");
  await page.getByRole("button", { name: "Start learning", exact: true }).click();
  await expect(page).toHaveURL(/\/learn$/);
  await expect(page.getByRole("link", { name: "Create a course" })).toBeVisible();
});

test("Observatory animation and pause", async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/?intro=1");
  await page.waitForTimeout(2800);
  const before = await page.locator(".glass-prerequisite").evaluate(el => getComputedStyle(el).transform);
  await page.waitForTimeout(350);
  const after = await page.locator(".glass-prerequisite").evaluate(el => getComputedStyle(el).transform);
  expect(after).not.toBe(before);
  await page.getByRole("button", { name: "Pause motion" }).click();
  expect(await page.locator(".glass-prerequisite").evaluate(el => getComputedStyle(el).animationPlayState)).toBe("paused");
  await capture(page, info, "hero-motion-paused");
});

test("EXAMPLE FIXTURE: five views and inspectable graph", async ({ page }, info) => {
  const server = phase10Scenario();
  const errors: string[] = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.addInitScript(value => localStorage.setItem("conceptlens:learner", value), learner);
  // Illustrative API fixture only; never imported into production.
  const concepts = ["CPU scheduling", "Processes and threads", "Context switching", "Scheduling criteria", "Scheduling algorithms", "Preemption", "Remaining time"].map((name, i) => ({ id: id(300+i), name, description: i === 0 ? "How an operating system decides which process runs on the CPU, and for how long." : `Example source-grounded description of ${name.toLowerCase()} for visual testing.`, citations: [citation] }));
  const graph = { concepts, prerequisites: concepts.slice(1).map((c,i) => ({ id:id(400+i), prerequisite_concept_id:c.id, target_concept_id:concepts[0].id, relation_type:"prerequisite", source_backed:i%2===0, confidence:null })) };
  await page.route(url => url.pathname.startsWith("/api/"), async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.pathname.endsWith("/concept-evidence")) return route.fulfill({ json:graph });
    const reply = server.handle(url.pathname.replace("/api", "") + url.search, request.method(), request.postDataJSON() ?? {});
    await route.fulfill({ status:reply.status, json:reply.body });
  });
  for (const name of ["workspace", "ask", "learn", "practice", "dashboard"]) {
    await page.goto(`/${name}`);
    await expect(page.getByRole("navigation", { name:"Principal navigation" })).toBeVisible();
    if (name === "ask") {
      await page.getByLabel("What would you like to understand?").fill("Why does scheduling depend on remaining time?");
      await page.getByRole("button", { name:"Ask ConceptLens" }).click();
      await expect(page.getByText("The source compares remaining execution time.")).toBeVisible();
    }
    if (name === "learn" || name === "dashboard") {
      if (name === "learn" && info.project.name === "mobile") await page.locator(".learn-atlas > summary").click();
      await expect(page.getByRole("heading", { name:"Concepts and prerequisites" })).toBeVisible();
      await page.getByRole("button", { name:/Remaining time/ }).click();
      await expect(page.locator(".concept-inspector h3")).toHaveText("Remaining time");
      await page.getByRole("button", { name:/CPU scheduling/ }).click();
      if (info.project.name === "desktop") await expect(page.locator(".concept-edges > path")).toHaveCount(6);
    }
    await capture(page, info, name, true);
  }
  if (info.project.name === "desktop") {
    await page.setViewportSize({width:834,height:1194});
    await page.goto("/learn");
    await expect(page.getByRole("heading", {name:"Concepts and prerequisites"})).toBeVisible();
    await capture(page, info, "tablet-learn", true);
  }
  expect(errors).toEqual([]);
});

test("Service failure keeps each route accessible and honest", async ({ page }, info) => {
  await page.route(url => url.pathname.startsWith("/api/"), route => route.abort());
  for (const path of ["workspace", "ask", "learn", "practice", "dashboard"]) {
    await page.goto(`/${path}`);
    await expect(page.getByRole("alert")).toContainText("couldn’t reach ConceptLens");
    await expect(page.locator(".page-heading h1")).toBeVisible();
  }
  await capture(page, info, "service-unavailable");
});

test("Live frontend: all routes render without API interception", async ({ page }, info) => {
  const health = await page.request.get("/api/health");
  console.log(`Actual backend health through Vite proxy: HTTP ${health.status()}`);
  for (const path of ["workspace", "ask", "learn", "practice", "dashboard"]) {
    await page.goto(`/${path}`);
    await expect(page.locator(".page-heading h1")).toBeVisible();
    if (!health.ok()) await expect(page.getByRole("alert").first()).toBeVisible();
    await capture(page, info, `live-${path}`);
  }
});
