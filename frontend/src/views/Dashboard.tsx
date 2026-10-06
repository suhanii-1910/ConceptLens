import { useCallback } from "react";
import {
  ArrowDown,
  ArrowRight,
  BookOpen,
  GitBranch,
  Layers,
  ShieldCheck,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { MasteryBand } from "../api/types";
import { useQuery } from "../hooks";
import { useLearning } from "../state";
import {
  Empty,
  ErrorNotice,
  Loading,
  NoCourse,
  PageHeading,
} from "../components/ui";

const bands: Record<MasteryBand, string> = {
  unseen: "Untested",
  needs_work: "Needs work",
  developing: "Developing",
  strong: "Strong",
  mastered: "Mastered",
};
export function Dashboard() {
  const { course } = useLearning();
  return (
    <>
      <PageHeading
        eyebrow="Dashboard / Your learning evidence"
        title="Progress you can point to."
        description="What you’ve demonstrated, what’s still untested, and the evidence behind your next step."
      />
      {course ? <EvidenceDashboard /> : <NoCourse />}
    </>
  );
}
function EvidenceDashboard() {
  const { course, learner, refs } = useLearning();
  const query = useQuery(
    useCallback(
      (signal: AbortSignal) => api.mastery(course!.id, learner, signal),
      [course, learner],
    ),
  );
  const relationships = useQuery(
    useCallback(
      async (signal: AbortSignal) => {
        if (!refs.diagnosis_id) return null;
        try {
          return await api.diagnosis(
            course!.id,
            learner,
            refs.diagnosis_id,
            signal,
          );
        } catch (error) {
          if (error instanceof ApiError && error.status === 404) return null;
          throw error;
        }
      },
      [course, learner, refs.diagnosis_id],
    ),
  );
  if (query.loading)
    return <Loading label="Reading your verified learning evidence…" />;
  if (query.error)
    return <ErrorNotice error={query.error} retry={query.reload} />;
  const concepts = query.data?.concepts ?? [];
  const observed = concepts.filter((concept) => concept.observation_count > 0);
  const observations = concepts.reduce(
    (sum, concept) => sum + concept.observation_count,
    0,
  );
  const target = concepts.find(
    (concept) => concept.concept_id === relationships.data?.target_concept_id,
  );
  return (
    <>
      <div className="metric-grid">
        <div className="metric">
          <Layers size={20} />
          <span>Concepts with evidence</span>
          <strong>
            {observed.length}
            <small> / {concepts.length}</small>
          </strong>
        </div>
        <div className="metric">
          <ShieldCheck size={20} />
          <span>Verified observations</span>
          <strong>{observations}</strong>
        </div>
        <div className="metric">
          <BookOpen size={20} />
          <span>Still untested</span>
          <strong>{concepts.length - observed.length}</strong>
        </div>
      </div>
      {observed.length === 0 && (
        <div className="cold-start">
          <span className="icon-tile">
            <BookOpen size={23} />
          </span>
          <div>
            <h2>A clean slate is a good place to start.</h2>
            <p>
              No learning evidence yet. Reading or saying “I understand” doesn’t
              change mastery.
            </p>
          </div>
          <Link to="/practice" className="button">
            Start with Practice <ArrowRight size={16} />
          </Link>
        </div>
      )}
      <div className="dashboard-layout">
        <section className="card mastery-card">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Concept by concept</p>
              <h2>Your evidence, in focus.</h2>
            </div>
          </div>
          {concepts.length ? (
            <ul className="mastery-list">
              {concepts.map((concept) => {
                const seen = concept.observation_count > 0;
                return (
                  <li key={concept.concept_id}>
                    <div className="mastery-title">
                      <strong>{concept.concept_name}</strong>
                      <span className={seen ? "mastery-value" : "untested"}>
                        {seen
                          ? `${Math.round(concept.mastery_probability * 100)}%`
                          : "Untested"}
                      </span>
                    </div>
                    {seen ? (
                      <>
                        <meter
                          min={0}
                          max={1}
                          value={concept.mastery_probability}
                          aria-label={`${concept.concept_name} estimated mastery`}
                        />
                        <div className="mastery-meta">
                          <span>
                            {bands[concept.mastery_band]} ·{" "}
                            {concept.observation_count} observations ·{" "}
                            {concept.correct_count} correct
                          </span>
                          {concept.updated_at && (
                            <span>
                              Updated{" "}
                              {new Date(
                                concept.updated_at,
                              ).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                        <details className="model-details">
                          <summary>Estimate details</summary>
                          <p>
                            Model: {concept.model_version}. Mastery is an
                            estimate from verified responses, not a certainty.
                          </p>
                        </details>
                      </>
                    ) : (
                      <p className="muted">
                        No observed responses. No performance estimate shown.
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          ) : (
            <Empty title="No course concepts are available yet.">
              Sources can still support Ask and Practice. Concept mastery needs
              curated course concepts and evidence links.
            </Empty>
          )}
          <p className="quiet-note">
            Estimates use the existing BKT learner model. Its defaults are
            uncalibrated; more evidence is more useful than a single score.
          </p>
        </section>
        <aside className="card relationship-panel">
          <GitBranch size={25} />
          <p className="eyebrow">Your current learning context</p>
          <h2>Ideas have foundations.</h2>
          {relationships.loading && (
            <Loading label="Reading related concepts…" />
          )}
          <ErrorNotice
            error={relationships.error}
            retry={relationships.reload}
          />
          {relationships.data && target ? (
            <div className="concept-map">
              <div className="concept-node target">
                <small>Target concept</small>
                <strong>{target.concept_name}</strong>
              </div>
              {relationships.data.prerequisites.length ? (
                <>
                  <ArrowDown className="map-arrow" size={23} />
                  <p className="map-label">Has recorded prerequisites</p>
                  {relationships.data.prerequisites.map((item) => (
                    <div className="concept-node" key={item.edge_id}>
                      <small>Prerequisite</small>
                      <strong>{item.name}</strong>
                    </div>
                  ))}
                </>
              ) : (
                <p>
                  No prerequisite relationships were returned for this
                  diagnosis.
                </p>
              )}
              <Link to="/learn" className="text-link">
                Return to this reasoning event <ArrowRight size={15} />
              </Link>
            </div>
          ) : (
            <p>
              A reasoning diagnosis can reveal related prerequisites here.
              There’s no course-wide graph available yet.
            </p>
          )}
          <div className="rule" />
          <p className="quiet-note">
            Only relationships returned for your current diagnosis appear here.
            Unseen connections are never filled in.
          </p>
        </aside>
      </div>
    </>
  );
}
