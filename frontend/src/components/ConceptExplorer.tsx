import { useCallback, useId, useState } from "react";
import { GitBranch, Layers, List, Network } from "lucide-react";
import { api } from "../api/client";
import type { ConceptGraph } from "../api/types";
import { useQuery } from "../hooks";
import { useLearning } from "../state";
import { Citations, Empty, ErrorNotice, Loading } from "./ui";

export function ConceptEvidencePanel() {
  const { course } = useLearning();
  const query = useQuery(useCallback((signal: AbortSignal) => api.graph(course!.id, signal), [course]));
  return <section className="card concept-observatory">
    {query.loading && <Loading label="Finding recorded concept relationships…"/>}
    <ErrorNotice error={query.error} retry={query.reload}/>
    {query.data && (query.data.concepts.length ? <ConceptExplorer graph={query.data}/> : <Empty title="Your constellation starts with evidence.">No concept graph is available for this course yet. Your sources can still support questions and practice.</Empty>)}
    <p className="quiet-note"><GitBranch size={14}/> A prerequisite relationship alone does not establish learner weakness. Observation counts and assessment evidence are shown separately.</p>
  </section>;
}

export function ConceptExplorer({ graph }: { graph: ConceptGraph }) {
  const [selected, setSelected] = useState<string>();
  const [view, setView] = useState<"map" | "list">(() => typeof window.matchMedia === "function" && window.matchMedia("(max-width: 760px)").matches ? "list" : "map");
  const marker = useId();
  const focus = graph.concepts.find(c => c.id === selected) ?? graph.concepts[0];
  // Larger graphs use the complete list, keeping labels readable instead of hiding nodes.
  const showMap = view === "map" && graph.concepts.length <= 9;
  const positions = (showMap ? graph.concepts : []).map((concept, i) => {
    if (i === 0) return { concept, x:50, y:50 };
    const slots = [[18,18],[50,18],[82,18],[18,82],[50,82],[82,82],[15,50],[85,50]];
    const [x,y] = graph.concepts.length <= 3 ? [i === 1 ? 25 : 75,18] : slots[i - 1];
    return { concept, x, y };
  });
  const connected = graph.prerequisites.filter(e => e.target_concept_id === focus.id || e.prerequisite_concept_id === focus.id);
  return <>
    <header className="concept-observatory-header"><div><p className="eyebrow">Knowledge Observatory / {graph.concepts.length} recorded concepts</p><h2>Concepts and prerequisites</h2></div><div className="view-switch" role="group" aria-label="Concept view"><button aria-pressed={showMap} onClick={() => setView("map")} disabled={graph.concepts.length > 9}><Network size={13}/>Map</button><button aria-pressed={!showMap} onClick={() => setView("list")}><List size={13}/>List</button></div></header>
    <div className="concept-explorer">
      {showMap ? <div className="concept-canvas" role="group" aria-label="Recorded concept map">
        <svg className="concept-edges" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true"><defs><marker id={marker} markerWidth="4" markerHeight="4" refX="3" refY="2" orient="auto"><path d="M0,0 L4,2 L0,4" fill="none" stroke="#568c7e" strokeWidth=".7"/></marker></defs>
          {graph.prerequisites.map(edge => {
            const from = positions.find(p => p.concept.id === edge.prerequisite_concept_id);
            const to = positions.find(p => p.concept.id === edge.target_concept_id);
            if (!from || !to) return null;
            const dx = to.x - from.x, dy = to.y - from.y;
            const factor = Math.max(0,1 - Math.min(12 / Math.max(Math.abs(dx),.01), 11 / Math.max(Math.abs(dy),.01)));
            return <path key={edge.id} d={`M${from.x},${from.y} Q${from.x},${from.y + dy * factor * .65} ${from.x + dx * factor},${from.y + dy * factor}`} stroke={edge.source_backed ? "#528e81" : "#b18c67"} strokeWidth=".25" strokeDasharray={edge.source_backed ? undefined : "1 1"} fill="none" markerEnd={`url(#${marker})`}/>;
          })}
        </svg>
        {positions.map(({concept,x,y}) => <button className="graph-concept" key={concept.id} style={{left:`${x}%`,top:`${y}%`}} aria-pressed={focus.id === concept.id} onClick={() => setSelected(concept.id)}><Layers size={20}/><span><strong>{concept.name}</strong><small>{concept.citations.length ? `${concept.citations.length} source ${concept.citations.length === 1 ? "reference" : "references"}` : "No source references"}</small></span></button>)}
      </div> : <div className="concept-list">{graph.concepts.map(concept => <button key={concept.id} aria-pressed={focus.id === concept.id} onClick={() => setSelected(concept.id)}><Layers size={17}/>{concept.name}</button>)}</div>}
      <aside className="concept-inspector" aria-live="polite"><p className="eyebrow">Concept in focus</p><h3>{focus.name}</h3><p>{focus.description || "No description has been recorded for this concept."}</p><Citations citations={focus.citations} compact/><div className="rule"/><details className="connection-details"><summary>{connected.length} recorded connections</summary>{connected.length ? <ul>{connected.map(edge => <li key={edge.id}>{graph.concepts.find(c => c.id === edge.prerequisite_concept_id)?.name ?? "Unavailable concept"} → {graph.concepts.find(c => c.id === edge.target_concept_id)?.name ?? "Unavailable concept"}<small>{edge.relation_type.replaceAll("_"," ")} · {edge.source_backed ? "Source-backed relationship" : "Recorded relationship; source backing not verified"}</small></li>)}</ul> : <p>No prerequisite relationships recorded for this idea.</p>}</details></aside>
    </div>
  </>;
}
