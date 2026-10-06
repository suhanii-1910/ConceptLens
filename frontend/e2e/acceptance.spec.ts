import { expect, test, type Page, type TestInfo } from "@playwright/test";
import { learner, question, scenario } from "../src/test/scenario";

async function capture(page: Page, info: TestInfo, name: string) {
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, 0));
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(overflow, `${name} should fit without horizontal page scrolling`).toBe(
    false,
  );
  await page.screenshot({
    path: info.outputPath(`${name}.png`),
    fullPage: true,
  });
  const focus =
    name === "04-learn-visual" || name === "06-transfer-check"
      ? ".teaching"
      : name === "07-learning-trace"
        ? ".trace-panel"
        : null;
  if (focus)
    await page
      .locator(focus)
      .screenshot({ path: info.outputPath(`${name}-detail.png`) });
}
const navigate = (page: Page, name: string) =>
  page
    .getByRole("navigation", { name: "Principal navigation" })
    .getByRole("link", { name, exact: true })
    .click();

test("API fixture: five-view judge journey, adaptive repair, transfer, trace and mastery", async ({
  page,
}, info) => {
  const server = scenario();
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  await page.addInitScript(
    (value) => localStorage.setItem("conceptlens:learner", value),
    learner,
  );
  await page.route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const request = route.request();
      const headers = request.headers();
      const body = headers["content-type"]?.includes("application/json")
        ? request.postDataJSON()
        : {};
      const result = server.handle(
        new URL(request.url()).pathname.replace("/api", ""),
        request.method(),
        body,
      );
      await route.fulfill({ status: result.status, json: result.body });
    },
  );
  await page.goto("/workspace");
  await expect(page.getByText("No sources yet.")).toBeVisible();
  await expect(page.getByRole("navigation").getByRole("link")).toHaveCount(5);
  await page.getByLabel("Upload course material").setInputFiles({
    name: "CPU Scheduling.pdf",
    mimeType: "",
    buffer: Buffer.from("test-only upload bytes"),
  });
  await page.getByRole("button", { name: "Process", exact: true }).click();
  await expect(page.getByText("Processed", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Index course material" }).click();
  await expect(page.getByText(/12 searchable evidence units/)).toBeVisible();
  await capture(page, info, "01-workspace");

  await navigate(page, "Ask");
  await page
    .getByLabel("What would you like to understand?")
    .fill("Explain FCFS scheduling");
  await page.getByRole("button", { name: "Ask ConceptLens" }).click();
  await expect(page.getByText(/FCFS runs each process/)).toBeVisible();
  await page.locator(".citation summary").click();
  await expect(page.getByText("Stored source location")).toBeVisible();
  await capture(page, info, "02-ask-citation");

  await navigate(page, "Learn");
  await page
    .getByLabel("What would you like to work on?")
    .fill("FCFS scheduling");
  await page.getByRole("button", { name: "Find me a problem" }).click();
  await expect(page.getByText(question.question_text)).toBeVisible();
  await expect(page.getByLabel(/Explain your thinking/)).toHaveCount(0);
  await page.getByRole("radio", { name: /The shortest process/ }).check();
  await page.getByRole("button", { name: "Record my answer" }).click();
  await page
    .getByLabel(/Explain your thinking/)
    .fill("I compare the two processes and choose by burst length.");
  await page.getByRole("button", { name: "Add a step" }).click();
  await page.getByLabel("Reasoning step 1").fill("I list both arrival times.");
  await page.getByRole("button", { name: "Add a step" }).click();
  await page
    .getByLabel("Reasoning step 2")
    .fill("I choose the shortest process first.");
  await page.getByRole("button", { name: "Debug my reasoning" }).click();
  await expect(
    page.getByText("Possible first break", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Verified probe explanation/)).toHaveCount(0);
  await capture(page, info, "03-learn-debugger");
  await page.getByRole("radio", { name: /Burst length/ }).check();
  await page.getByRole("button", { name: "Test the hypothesis" }).click();
  await page.getByRole("button", { name: "Start guided repair" }).click();
  await expect(
    page.getByRole("heading", { name: "Back to the source" }),
  ).toBeVisible();
  await expect(
    page.getByRole("region", { name: "Learning Trace" }),
  ).toHaveCount(0);
  await page.getByRole("button", { name: "Still confused" }).click();
  await expect(page.getByText("From arrival to execution")).toBeVisible();
  await capture(page, info, "04-learn-visual");
  await page.getByRole("button", { name: "Still confused" }).click();
  await page.getByRole("radio", { name: /The shortest process/ }).check();
  await page.getByRole("button", { name: "Check this prerequisite" }).click();
  await expect(
    page.getByText(/Verified prerequisite explanation/),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /Continue anyway/ }),
  ).toBeVisible();
  await capture(page, info, "05-prerequisite-choices");
  await page.getByRole("button", { name: /60-second recap/ }).click();
  await expect(
    page.getByRole("heading", { name: "Your 60-second recap" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "I understand" }).click();
  await expect(
    page.getByRole("heading", { name: "One example, step by step" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "I understand" }).click();
  await expect(
    page.getByRole("heading", { name: "Transfer Check", exact: true }),
  ).toBeVisible();
  await expect(page.getByText(/Verified transfer explanation/)).toHaveCount(0);
  await capture(page, info, "06-transfer-check");
  await page.getByRole("radio", { name: /The first arrival/ }).check();
  await page.getByRole("button", { name: "Verify my understanding" }).click();
  await expect(page.getByText(/Verified transfer explanation/)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Understanding, put to the test." }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /Why did ConceptLens do this/ })
    .click();
  await expect(page.getByText("What has been verified?")).toBeVisible();
  await expect(page.getByText("Not verified", { exact: true })).toHaveCount(1);
  await capture(page, info, "07-learning-trace");

  await navigate(page, "Dashboard");
  await expect(page.getByText("62%", { exact: true })).toBeVisible();
  await expect(page.getByText("Untested", { exact: true })).toBeVisible();
  await capture(page, info, "08-dashboard");
  await navigate(page, "Practice");
  await page
    .getByLabel("What would you like to work on?")
    .fill("Arrival order");
  await page.getByRole("button", { name: "Find me a problem" }).click();
  await page.getByRole("radio", { name: /The shortest process/ }).check();
  await page.getByRole("button", { name: "Check my answer" }).click();
  await expect(page.getByText(/Verified assessment explanation/)).toBeVisible();
  await capture(page, info, "09-practice");
  expect(errors).toEqual([]);
});

test("API fixture: honest loading, provider failure and evidence refusal", async ({
  page,
}, info) => {
  const server = scenario();
  let fail = true;
  let releaseAnswer!: () => void;
  const pendingAnswer = new Promise<void>((resolve) => {
    releaseAnswer = resolve;
  });
  await page.route(
    (url) => url.pathname.startsWith("/api/"),
    async (route) => {
      const request = route.request();
      const path = new URL(request.url()).pathname.replace("/api", "");
      if (path.endsWith("/ask") && fail) {
        await pendingAnswer;
        return route.fulfill({
          status: 503,
          json: { detail: "Answer generation is not configured." },
        });
      }
      const body = request.postData() ? request.postDataJSON() : {};
      const result = server.handle(path, request.method(), body);
      await route.fulfill({ status: result.status, json: result.body });
    },
  );
  await page.goto("/ask");
  await page
    .getByLabel("What would you like to understand?")
    .fill("Unsupported topic");
  await page.getByRole("button", { name: "Ask ConceptLens" }).click();
  await expect(page.getByRole("status")).toContainText(
    "Finding relevant evidence in your material…",
  );
  await expect(
    page.getByRole("button", { name: "Ask ConceptLens" }),
  ).toBeDisabled();
  await capture(page, info, "12-loading");
  releaseAnswer();
  await expect(page.getByRole("alert")).toContainText(
    "Answer generation is not configured.",
  );
  await capture(page, info, "10-provider-error");
  fail = false;
  await page.getByRole("button", { name: "Ask ConceptLens" }).click();
  await expect(
    page.getByText("Your sources do not support this topic."),
  ).toBeVisible();
  await capture(page, info, "11-evidence-boundary");
});

test("live backend: proxy health and all five views without API fixtures", async ({
  page,
}, info) => {
  test.skip(
    process.env.CONCEPTLENS_LIVE_SMOKE !== "1",
    "Opt in with the actual backend running on port 8000.",
  );
  const health = await page.request.get("/api/health");
  expect(await health.json()).toEqual({ status: "ok" });
  const response = await page.request.get("/api/courses");
  expect(response.ok()).toBe(true);
  const courses = (await response.json()) as { id: string; name: string }[];
  for (const name of ["Workspace", "Ask", "Learn", "Practice", "Dashboard"]) {
    await page.goto(`/${name.toLowerCase()}`);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
    await expect(
      page.getByText("Opening your learning workspace…"),
    ).toHaveCount(0);
    if (name === "Dashboard")
      await expect(
        page.getByText("Reading your verified learning evidence…"),
      ).toHaveCount(0);
    await expect(page.getByRole("alert")).toHaveCount(0);
    await capture(page, info, `live-${name.toLowerCase()}`);
  }
  if (courses.length && process.env.CONCEPTLENS_EXPECT_UNCONFIGURED === "1") {
    await navigate(page, "Learn");
    await page
      .getByLabel("What would you like to work on?")
      .fill("FCFS scheduling");
    const responsePromise = page.waitForResponse(
      (response) => response.url().endsWith("/assessments/generate"),
      { timeout: 60_000 },
    );
    await page.getByRole("button", { name: "Find me a problem" }).click();
    const generated = await responsePromise;
    if (generated.status() === 503) {
      await expect(page.getByRole("alert")).toContainText(
        "Assessment generation is not configured.",
      );
    } else {
      // An empty course can be declined before any provider call is needed.
      expect(generated.status()).toBe(200);
      expect((await generated.json()).status).toBe("declined");
      await expect(
        page.getByText("Your material doesn’t support an answer yet."),
      ).toBeVisible();
    }
    await capture(page, info, "live-evidence-or-provider-boundary");
  }
});
