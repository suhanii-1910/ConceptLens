import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ConceptExplorer } from "../components/ConceptExplorer";
import type { ConceptGraph } from "../api/types";

const graph: ConceptGraph = {
  concepts: [
    { id:"process", name:"Processes", description:"An executing program.", citations:[] },
    { id:"schedule", name:"Scheduling", description:"Choosing a process to run.", citations:[] },
    { id:"unconnected", name:"Unconnected idea", description:null, citations:[] },
  ],
  prerequisites: [{ id:"edge", prerequisite_concept_id:"process", target_concept_id:"schedule", relation_type:"prerequisite", source_backed:false, confidence:null }],
};

describe("Observatory evidence map", () => {
  it("draws only supplied edges and exposes source uncertainty", async () => {
    const user = userEvent.setup();
    const { container } = render(<ConceptExplorer graph={graph}/>);
    expect(container.querySelectorAll(".concept-edges > path")).toHaveLength(1);
    await user.click(screen.getByRole("button", { name:/Scheduling/ }));
    const inspector = screen.getByRole("complementary");
    expect(within(inspector).getByRole("heading")).toHaveTextContent("Scheduling");
    await user.click(screen.getByText("1 recorded connections"));
    expect(within(inspector).getByText(/source backing not verified/)).toBeVisible();
    await user.click(screen.getByRole("button", { name:/Unconnected idea/ }));
    expect(within(inspector).getByText("No prerequisite relationships recorded for this idea.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/mastered|weakness detected|\d+%/i);
  });

  it("preserves selected evidence when switching between map and list", async () => {
    const user = userEvent.setup();
    render(<ConceptExplorer graph={graph}/>);
    await user.click(screen.getByRole("button", { name:/Scheduling/ }));
    await user.click(screen.getByRole("button", { name:"List" }));
    expect(screen.getByRole("button", { name:"Scheduling" })).toHaveAttribute("aria-pressed","true");
    expect(screen.getByText("Choosing a process to run.")).toBeVisible();
    await user.click(screen.getByRole("button", { name:"Map" }));
    expect(screen.getByRole("button", { name:/Scheduling/ })).toHaveAttribute("aria-pressed","true");
  });

  it("keeps every concept accessible in larger graphs", () => {
    const concepts = Array.from({length:12},(_,i) => ({id:String(i),name:`Concept ${i}`,description:null,citations:[]}));
    render(<ConceptExplorer graph={{concepts,prerequisites:[]}}/>);
    expect(screen.getByRole("button", {name:"Map"})).toBeDisabled();
    expect(screen.getAllByRole("button", {name:/Concept \d/})).toHaveLength(12);
  });
});
