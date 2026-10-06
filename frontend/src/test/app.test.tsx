import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { learnerUUID } from "../state";
import { validReasoning } from "../views/Learn";
import {
  course,
  otherCourse,
  learner,
  question,
  attempt,
  diagnosis,
  session,
  scenario,
  id,
  date,
} from "./scenario";

afterEach(() => vi.unstubAllGlobals());
function mount(path = "/learn", server = scenario(), restore = false) {
  localStorage.setItem("conceptlens:learner", learner);
  if (restore)
    localStorage.setItem(
      `conceptlens:journey:${learner}:${course.id}`,
      JSON.stringify({
        question_id: question.id,
        attempt_id: attempt.attempt_id,
        diagnosis_id: diagnosis.id,
        session_id: id(70),
      }),
    );
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    const body =
      typeof options?.body === "string" ? JSON.parse(options.body) : {};
    const reply = server.handle(url.replace("/api", ""), options?.method, body);
    return new Response(JSON.stringify(reply.body), { status: reply.status });
  });
  vi.stubGlobal("fetch", fetcher);
  const result = render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>,
  );
  return { server, fetcher, user: userEvent.setup(), ...result };
}
async function generate(user: ReturnType<typeof userEvent.setup>) {
  await user.type(
    await screen.findByLabelText("What would you like to work on?"),
    "FCFS scheduling",
  );
  await user.click(screen.getByRole("button", { name: "Find me a problem" }));
  await screen.findByText(question.question_text);
}
describe("application contracts", () => {
  it.each([
    ["sixty_second_recap", "60-second recap", "Your 60-second recap"],
    [
      "practice_prerequisite",
      "Practice prerequisite",
      "Practice the prerequisite",
    ],
    ["continue_anyway", "Continue anyway", "One example, step by step"],
  ])(
    "posts %s and renders only the returned strategy",
    async (choice, label, nextHeading) => {
      const server = scenario();
      server.setSession({
        ...session("prerequisite_probe"),
        current_action: "prerequisite_choice",
        prerequisite_choices: [
          "sixty_second_recap",
          "practice_prerequisite",
          "continue_anyway",
        ],
      });
      const { user } = mount("/learn", server, true);
      await user.click(
        await screen.findByRole("button", { name: new RegExp(label) }),
      );
      await screen.findByRole("heading", { name: nextHeading });
      expect(
        server.calls.find((call) => call.path.endsWith("/prerequisite-choice"))
          ?.body,
      ).toEqual({ intervention_id: id(51), choice });
    },
  );
  it("lets the learner add reasoning to the same real attempt when the server requests it", async () => {
    const server = scenario();
    server.setSession({
      ...session(),
      current_action: "collect_more_reasoning",
      status: "diagnosis_not_confirmed",
      current_intervention: null,
    });
    const { user } = mount("/learn", server, true);
    await user.click(
      await screen.findByRole("button", { name: "Add more reasoning" }),
    );
    await screen.findByLabelText(/Explain your thinking/);
    expect(
      JSON.parse(
        localStorage.getItem(`conceptlens:journey:${learner}:${course.id}`)!,
      ),
    ).toEqual({ question_id: question.id, attempt_id: attempt.attempt_id });
    expect(
      screen.queryByRole("button", { name: "Record my answer" }),
    ).not.toBeInTheDocument();
  });
  it("has exactly five principal destinations and keeps one opaque learner UUID", async () => {
    const first = learnerUUID();
    expect(learnerUUID()).toBe(first);
    const { user } = mount("/workspace");
    const navigation = screen.getByRole("navigation", {
      name: "Principal navigation",
    });
    expect(
      within(navigation)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["Workspace", "Ask", "Learn", "Practice", "Dashboard"]);
    await user.click(
      within(navigation).getByRole("link", { name: "Dashboard" }),
    );
    await screen.findByText("Your evidence, in focus.");
    expect(localStorage.getItem("conceptlens:learner")).toBe(learner);
  });
  it("isolates attempt, diagnosis, and session references when switching courses and learners", async () => {
    const server = scenario();
    server.setSession(session());
    const { user } = mount("/learn", server, true);
    await screen.findByRole("heading", { name: "Back to the source" });
    const before = server.calls.length;
    await user.selectOptions(
      screen.getByLabelText("Active course"),
      otherCourse.id,
    );
    await screen.findByLabelText("What would you like to work on?");
    expect(
      screen.queryByText("Why did ConceptLens do this?"),
    ).not.toBeInTheDocument();
    expect(
      server.calls
        .slice(before)
        .some((call) =>
          /reasoning-diagnoses|learning-sessions|assessments\/questions/.test(
            call.path,
          ),
        ),
    ).toBe(false);
    expect(
      JSON.parse(
        localStorage.getItem(
          `conceptlens:journey:${learner}:${otherCourse.id}`,
        )!,
      ),
    ).toEqual({});
    await user.selectOptions(screen.getByLabelText("Active course"), course.id);
    await screen.findByRole("heading", { name: "Back to the source" });
    await user.click(screen.getByText("Your learning profile"));
    await user.click(
      screen.getByRole("button", { name: "Reset demo learner" }),
    );
    await user.click(screen.getByRole("button", { name: "Reset learner" }));
    await screen.findByLabelText("What would you like to work on?");
    expect(localStorage.getItem("conceptlens:learner")).not.toBe(learner);
    expect(
      screen.queryByRole("heading", { name: "Back to the source" }),
    ).not.toBeInTheDocument();
  });
  it("uploads a supported extension with empty MIME, then processes and indexes real responses", async () => {
    const { user, fetcher } = mount("/workspace");
    await screen.findByText("No sources yet.");
    fireEvent.change(screen.getByLabelText("Upload course material"), {
      target: { files: [new File(["pdf bytes"], "lecture.PDF", { type: "" })] },
    });
    await screen.findByText("Ready to process");
    const call = fetcher.mock.calls.find(
      ([, options]) => options?.body instanceof FormData,
    );
    expect((call?.[1]?.body as FormData).get("file")).toHaveProperty(
      "type",
      "application/pdf",
    );
    await user.click(screen.getByRole("button", { name: "Process" }));
    await screen.findByText("Processed");
    expect(screen.getByText("12 text evidence units")).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "Index course material" }),
    );
    await screen.findByText("12 searchable evidence units · 12 newly indexed.");
  });
  it("renders backend processing and failure states without inventing progress", async () => {
    const server = scenario();
    server.setSources(
      ["processing", "failed"].map((status, i) => ({
        id: id(12 + i),
        course_id: course.id,
        original_filename: `lecture-${i}.pdf`,
        source_type: "pdf",
        processing_status: status as "processing" | "failed",
        created_at: date,
      })),
    );
    mount("/workspace", server);
    expect(
      await screen.findByRole("button", { name: "Processing…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Retry processing" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("button", { name: "Index course material" }),
    ).toBeDisabled();
  });
  it.each([
    ["Just Answer", "just_answer"],
    ["Explain It", "explain"],
    ["Guide Me With Questions", "guide"],
  ])(
    "uses the canonical Ask mode %s and displays exact citations",
    async (label, mode) => {
      const { user, server } = mount("/ask");
      await user.click(await screen.findByRole("button", { name: label }));
      await user.type(
        screen.getByLabelText("What would you like to understand?"),
        "Explain FCFS",
      );
      await user.click(screen.getByRole("button", { name: "Ask ConceptLens" }));
      await screen.findByText(/FCFS runs each process/);
      expect(screen.getByText("CPU Scheduling.pdf")).toBeInTheDocument();
      expect(screen.getAllByText("Page 4")[0]).toBeInTheDocument();
      expect(
        server.calls.find((call) => call.path.endsWith("/ask"))?.body.mode,
      ).toBe(mode);
    },
  );
  it("presents an evidence refusal as a useful state", async () => {
    const { user } = mount("/ask");
    await user.type(
      await screen.findByLabelText("What would you like to understand?"),
      "Unsupported topic",
    );
    await user.click(screen.getByRole("button", { name: "Ask ConceptLens" }));
    expect(
      await screen.findByText("Your sources do not support this topic."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("From your course material"),
    ).not.toBeInTheDocument();
  });
  it("requires a real assessment attempt before reasoning, restores it, then diagnoses and probes", async () => {
    const { user, server, unmount } = mount();
    await generate(user);
    expect(
      screen.queryByLabelText(/Explain your thinking/),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(attempt.explanation)).not.toBeInTheDocument();
    await user.click(
      screen.getByRole("radio", { name: /The shortest process/ }),
    );
    await user.click(screen.getByRole("button", { name: "Record my answer" }));
    await screen.findByText(attempt.explanation);
    expect(
      server.calls.some((call) => call.path.endsWith("/reasoning-diagnoses")),
    ).toBe(false);
    unmount();
    const remounted = mount("/learn", server);
    await remounted.user.type(
      await screen.findByLabelText(/Explain your thinking/),
      "I choose the shortest process first.",
    );
    await remounted.user.click(
      screen.getByRole("button", { name: "Debug my reasoning" }),
    );
    await screen.findByText("Possible hypothesis");
    expect(
      server.calls.find((call) => call.path.endsWith("/reasoning-diagnoses"))
        ?.body.attempt_id,
    ).toBe(attempt.attempt_id);
    expect(
      screen.queryByText(/Verified probe explanation/),
    ).not.toBeInTheDocument();
    await remounted.user.click(
      screen.getByRole("radio", { name: /Burst length/ }),
    );
    await remounted.user.click(
      screen.getByRole("button", { name: "Test the hypothesis" }),
    );
    await screen.findByText(
      "Verified probe explanation: arrival time determines FCFS order.",
    );
    expect(
      server.calls.some(
        (call) =>
          call.method === "GET" &&
          call.path.endsWith(`/reasoning-diagnoses/${diagnosis.id}`),
      ),
    ).toBe(true);
    await remounted.user.click(
      screen.getByRole("button", { name: "Start guided repair" }),
    );
    await screen.findByRole("heading", { name: "Back to the source" });
    expect(screen.getByText(/Verified probe explanation/)).toBeInTheDocument();
    expect(
      screen.queryByRole("region", { name: "Learning Trace" }),
    ).not.toBeInTheDocument();
    expect(server.calls.some((call) => call.path.endsWith("/trace"))).toBe(
      false,
    );
    await remounted.user.click(
      screen.getByRole("button", { name: /Why did ConceptLens do this/ }),
    );
    await screen.findByText("What has been verified?");
    expect(screen.getAllByText("Not verified")).toHaveLength(2);
    expect(screen.getAllByText("Verified", { exact: true })).toHaveLength(4);
  });
  it.each(["feedback", "prerequisite-choice", "transfer-check/attempts"])(
    "recovers a stale %s by GETting the server session",
    async (endpoint) => {
      const server = scenario();
      const current =
        endpoint === "feedback"
          ? session()
          : endpoint === "prerequisite-choice"
            ? {
                ...session("prerequisite_probe"),
                current_action: "prerequisite_choice" as const,
                prerequisite_choices: ["continue_anyway" as const],
              }
            : session("transfer_check");
      server.setSession(current);
      server.conflict(endpoint);
      const { user } = mount("/learn", server, true);
      if (endpoint === "feedback")
        await user.click(
          await screen.findByRole("button", { name: "Still confused" }),
        );
      else if (endpoint === "prerequisite-choice")
        await user.click(
          await screen.findByRole("button", { name: /Continue anyway/ }),
        );
      else {
        await user.click(
          await screen.findByRole("radio", { name: /The first arrival/ }),
        );
        await user.click(
          screen.getByRole("button", { name: "Verify my understanding" }),
        );
      }
      await screen.findByText(
        "This learning step changed. You’re now seeing the latest saved step.",
      );
      expect(
        screen.getByRole("heading", { name: "Let’s look at this visually." }),
      ).toBeInTheDocument();
      expect(screen.getByText("P2 arrives · 2 ms")).toBeInTheDocument();
      const index = server.calls.findIndex(
        (call) => call.method === "POST" && call.path.endsWith(endpoint),
      );
      expect(server.calls[index + 1].path).toBe(
        `/courses/${course.id}/learners/${learner}/learning-sessions/${id(70)}`,
      );
      expect(server.calls[index + 1].method).toBe("GET");
    },
  );
  it("keeps a verified Transfer Check result visible after the server completes the session", async () => {
    const server = scenario();
    server.setSession(session("transfer_check"));
    const { user } = mount("/learn", server, true);
    expect(
      await screen.findByRole("heading", { name: "Transfer Check" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(/Verified transfer explanation/),
    ).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /The first arrival/ }));
    await user.click(
      screen.getByRole("button", { name: "Verify my understanding" }),
    );
    expect(
      await screen.findByText(
        "Verified transfer explanation: arrival order still controls the new situation.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Understanding, put to the test." }),
    ).toBeInTheDocument();
    expect(screen.getByText(/62%/)).toBeInTheDocument();
  });
  it("uses backend Practice grading even when a selected index looks like the key", async () => {
    const { user, server } = mount("/practice");
    await generate(user);
    expect(screen.queryByText(attempt.explanation)).not.toBeInTheDocument();
    await user.click(screen.getByRole("radio", { name: /The first arrival/ }));
    await user.click(screen.getByRole("button", { name: "Check my answer" }));
    await screen.findByText(attempt.explanation);
    expect(screen.getByText("Incorrect response.")).toBeInTheDocument();
    expect(
      server.calls.find((call) => call.path.endsWith("/attempts"))?.body
        .selected_option_index,
    ).toBe(0);
  });
  it("shows Untested rather than the initial BKT probability", async () => {
    mount("/dashboard");
    await screen.findByText("Your evidence, in focus.");
    expect(screen.getAllByText("Untested", { exact: true })).toHaveLength(2);
    expect(screen.queryByText("20%")).not.toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
  });
  it("clears missing saved records instead of retaining a phantom session", async () => {
    const server = scenario();
    const original = server.handle;
    server.handle = (path, ...rest) =>
      path.includes("/assessments/questions/")
        ? { status: 404, body: { detail: "Question not found." } }
        : original(path, ...rest);
    mount("/learn", server, true);
    await screen.findByText(
      "The saved problem is no longer available. Start with a fresh one.",
    );
    await waitFor(() =>
      expect(
        JSON.parse(
          localStorage.getItem(`conceptlens:journey:${learner}:${course.id}`)!,
        ),
      ).toEqual({}),
    );
  });
});
describe("Phase 6 reasoning limits", () => {
  it("counts Unicode code points like the Python schema", () => {
    expect(validReasoning("😀".repeat(8000), [])).toBe(true);
    expect(validReasoning("", ["😀".repeat(1000)])).toBe(true);
    expect(validReasoning("😀".repeat(8001), [])).toBe(false);
  });
  it("requires content, rejects blank steps, and matches the individual and combined bounds", () => {
    expect(validReasoning("", [])).toBe(false);
    expect(validReasoning("reasoning", [" "])).toBe(false);
    expect(validReasoning("a".repeat(8000), [])).toBe(true);
    expect(validReasoning("a".repeat(8001), [])).toBe(false);
    expect(validReasoning("", Array(20).fill("step"))).toBe(true);
    expect(validReasoning("", Array(21).fill("step"))).toBe(false);
    expect(validReasoning("", ["a".repeat(1000)])).toBe(true);
    expect(validReasoning("", ["a".repeat(1001)])).toBe(false);
    expect(
      validReasoning("a".repeat(8000), Array(4).fill("b".repeat(1000))),
    ).toBe(true);
    expect(
      validReasoning("a".repeat(8000), [
        ...Array(4).fill("b".repeat(1000)),
        "c",
      ]),
    ).toBe(false);
  });
});
