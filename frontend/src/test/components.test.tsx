import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ReasoningDebugger } from "../components/Reasoning";
import { Teaching, choiceLabels } from "../components/Teaching";
import { TraceContent } from "../components/TracePanel";
import { diagnosis, session, trace } from "./scenario";
import type { Choice, DiagnosisStatus } from "../api/types";

describe("evidence rendering", () => {
  it("highlights only the supported first break, with no correctness labels on earlier steps", () => {
    const { container } = render(<ReasoningDebugger diagnosis={diagnosis} />);
    expect(container.querySelectorAll("mark")).toHaveLength(1);
    expect(container.querySelector("mark")).toHaveTextContent(
      "shortest process",
    );
    expect(container.querySelector(".reasoning-sequence li")).not.toHaveClass(
      "possible-break",
    );
    expect(screen.queryByText("Correct")).not.toBeInTheDocument();
    expect(screen.getByText("Possible hypothesis")).toBeInTheDocument();
  });
  it.each<DiagnosisStatus>([
    "no_clear_break",
    "insufficient_reasoning",
    "insufficient_evidence",
  ])("renders %s without inventing a hypothesis", (status) => {
    render(
      <ReasoningDebugger
        diagnosis={{
          ...diagnosis,
          status,
          hypothesis_text: null,
          first_break_excerpt: null,
          first_break_step_index: null,
        }}
      />,
    );
    expect(screen.getByText("What the evidence says")).toBeInTheDocument();
    expect(screen.queryByText("Possible hypothesis")).not.toBeInTheDocument();
  });
  it.each<Choice>([
    "sixty_second_recap",
    "practice_prerequisite",
    "continue_anyway",
  ])(
    "sends the real prerequisite choice %s without local advancement",
    async (choice) => {
      const onChoice = vi.fn();
      render(
        <MemoryRouter>
          <Teaching
            session={{
              ...session("prerequisite_probe"),
              current_action: "prerequisite_choice",
              prerequisite_choices: [
                "sixty_second_recap",
                "practice_prerequisite",
                "continue_anyway",
              ],
            }}
            diagnosis={diagnosis}
            busy={false}
            onChoice={onChoice}
            onFeedback={vi.fn()}
            onAttempt={vi.fn()}
            onRestart={vi.fn()}
            onRevise={vi.fn()}
          />
        </MemoryRouter>,
      );
      await userEvent.click(
        screen.getByRole("button", { name: new RegExp(choiceLabels[choice]) }),
      );
      expect(onChoice).toHaveBeenCalledWith(choice);
      expect(
        screen.getByText("A quick detour could help."),
      ).toBeInTheDocument();
    },
  );
  it("renders structured visuals as text and never interprets HTML in model content", () => {
    const current = session("visual_explanation");
    const payload = current.current_intervention!.payload!;
    payload.body = "<img src=x onerror=alert(1)>";
    payload.visual!.steps[0].annotation = "<script>window.evil=true</script>";
    const { container } = render(
      <MemoryRouter>
        <Teaching
          session={current}
          diagnosis={diagnosis}
          busy={false}
          onChoice={vi.fn()}
          onFeedback={vi.fn()}
          onAttempt={vi.fn()}
          onRestart={vi.fn()}
          onRevise={vi.fn()}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText(payload.body)).toBeInTheDocument();
    expect(
      screen.getByText(payload.visual!.steps[0].annotation),
    ).toBeInTheDocument();
    expect(container.querySelector("script, img")).toBeNull();
    expect(screen.getByText("From arrival to execution")).toBeInTheDocument();
  });
  it("displays false proof values as Not verified", () => {
    render(<TraceContent trace={trace()} />);
    expect(screen.getAllByText("Not verified")).toHaveLength(2);
    expect(screen.getAllByText("Verified", { exact: true })).toHaveLength(4);
  });
});
