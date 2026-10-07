import { SourceInventory } from "../components/SourceViewer";
import { useCallback, useRef, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  FileText,
  FolderPlus,
  Plus,
  RefreshCw,
  Upload,
  Video,
} from "lucide-react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api/client";
import type { IndexingResult, ProcessingResult, Source } from "../api/types";
import { useQuery, useTask } from "../hooks";
import { useLearning } from "../state";
import {
  Button,
  Empty,
  ErrorNotice,
  Loading,
  PageHeading,
} from "../components/ui";

export function Workspace() {
  const { course, coursesChanged } = useLearning();
  const [creating, setCreating] = useState(!course);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const creation = useTask();
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const result = await creation.run((signal) =>
      api.createCourse(name.trim(), description.trim(), signal),
    );
    if (result) {
      coursesChanged(result);
      setCreating(false);
    }
  };
  return (
    <>
      <PageHeading
        eyebrow="Workspace / Your knowledge base"
        title="Good learning starts with your sources."
        description="Bring your course material together. Every answer and learning step starts here."
        action={
          <Button
            className="secondary"
            onClick={() => setCreating((value) => !value)}
          >
            <Plus size={17} /> New course
          </Button>
        }
      />
      {creating && (
        <section className="card">
          <div className="section-heading">
            <FolderPlus size={24} />
            <h2>Create a course</h2>
          </div>
          <form onSubmit={submit}>
            <label htmlFor="course-name">Course name</label>
            <input
              id="course-name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              required
              maxLength={255}
              disabled={creation.busy}
              placeholder="Name your course"
            />
            <label htmlFor="course-description">
              A short description <span className="muted">(optional)</span>
            </label>
            <textarea
              id="course-description"
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              rows={2}
              disabled={creation.busy}
            />
            <div className="form-footer">
              <span />
              <Button
                type="submit"
                busy={creation.busy}
                disabled={!name.trim()}
              >
                Create course <ArrowRight size={16} />
              </Button>
            </div>
          </form>
          <ErrorNotice error={creation.error} />
        </section>
      )}
      {course ? (
        <SourceWorkspace key={course.id} />
      ) : (
        !creating && (
          <Empty
            title="Your first course starts here."
            action={
              <Button onClick={() => setCreating(true)}>Create a course</Button>
            }
          >
            Add a course to give your source material a home.
          </Empty>
        )
      )}
    </>
  );
}
function SourceWorkspace() {
  const { course } = useLearning();
  const query = useQuery(
    useCallback(
      (signal: AbortSignal) => api.sources(course!.id, signal),
      [course],
    ),
  );
  const upload = useTask(),
    process = useTask(),
    index = useTask();
  const [dragging, setDragging] = useState(false);
  const [uploadName, setUploadName] = useState("");
  const [processing, setProcessing] = useState<string>();
  const [results, setResults] = useState<Record<string, ProcessingResult>>({});
  const [indexed, setIndexed] = useState<IndexingResult>();
  const [notice, setNotice] = useState("");
  const picker = useRef<HTMLInputElement>(null);
  const uploadFile = async (file?: File) => {
    if (!file || upload.busy) return;
    setUploadName(file.name);
    setNotice("");
    const result = await upload.run((signal) => {
      const typeByExtension: Record<string, string> = {
        pdf: "application/pdf",
        pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        mp4: "video/mp4",
      };
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      const type = typeByExtension[extension];
      if (!type) throw new ApiError(415);
      // Browsers sometimes omit or misidentify MIME. Normalize only supported
      // extensions; the backend still validates and processes the actual bytes.
      const uploadFile =
        file.type === type
          ? file
          : new File([file], file.name, {
              type,
              lastModified: file.lastModified,
            });
      return api.upload(course!.id, uploadFile, signal);
    });
    if (result) {
      setNotice(
        `${result.original_filename} is in your course. Current status: ${result.processing_status}.`,
      );
      query.reload();
      setIndexed(undefined);
    }
    if (picker.current) picker.current.value = "";
  };
  const processSource = async (source: Source) => {
    setProcessing(source.id);
    setNotice("");
    const result = await process.run((signal) =>
      api.process(course!.id, source.id, signal),
    );
    if (result) {
      setResults((values) => ({ ...values, [source.id]: result }));
      setIndexed(undefined);
    }
    query.reload();
    setProcessing(undefined);
  };
  const indexSources = async () => {
    const result = await index.run((signal) => api.index(course!.id, signal));
    if (result) setIndexed(result);
  };
  return (
    <>
      <div className="workspace-grid">
        <section className="card source-panel">
          <div className="section-heading">
            <div className="icon-tile">
              <BookOpen size={20} />
            </div>
            <div>
              <p className="eyebrow">Course library</p>
              <h2>{course!.name}</h2>
            </div>
            <Button
              className="icon-button secondary"
              aria-label="Refresh source list"
              onClick={query.reload}
              disabled={query.loading}
            >
              <RefreshCw size={16} />
            </Button>
          </div>
          <div
            className={`dropzone ${dragging ? "dragging" : ""}`}
            onDragOver={(event) => {
              event.preventDefault();
              setDragging(true);
            }}
            onDragLeave={() => setDragging(false)}
            onDrop={(event) => {
              event.preventDefault();
              setDragging(false);
              if (event.dataTransfer.files.length > 1) {
                setNotice(
                  "Choose one file at a time so each upload is easy to follow.",
                );
                return;
              }
              void uploadFile(event.dataTransfer.files[0]);
            }}
          >
            <Upload size={28} aria-hidden="true" />
            <h3>Make it your material.</h3>
            <p>Drop a source here, or choose a file.</p>
            <Button
              className="secondary"
              busy={upload.busy}
              onClick={() => picker.current?.click()}
            >
              Choose file
            </Button>
            <input
              className="sr-only"
              aria-label="Upload course material"
              ref={picker}
              type="file"
              accept=".pdf,.pptx,.mp4"
              disabled={upload.busy}
              onChange={(event) => void uploadFile(event.target.files?.[0])}
            />
            <small>PDF documents · PowerPoint decks · MP4 lectures</small>
          </div>
          {upload.busy && (
            <p role="status" className="notice">
              Uploading {uploadName}…
            </p>
          )}
          {notice && (
            <p role="status" className="quiet-note">
              {notice}
            </p>
          )}
          <ErrorNotice error={upload.error || process.error} />
          {query.loading && <Loading label="Reading your course library…" />}
          <ErrorNotice error={query.error} retry={query.reload} />
          {query.data &&
            (query.data.length ? (
              <ul className="source-list">
                {query.data.map((source) => (
                  <li key={source.id}>
                    <div className={`file-icon ${source.source_type}`}>
                      {source.source_type === "video" ? (
                        <Video size={21} />
                      ) : (
                        <FileText size={21} />
                      )}
                    </div>
                    <div className="source-info">
                      <strong>{source.original_filename}</strong>
                      <SourceInventory course={source.course_id} source={source.id}/>
                      <small>
                        {source.source_type.toUpperCase()} · Added{" "}
                        {new Date(source.created_at).toLocaleDateString()}
                      </small>
                      <span className={`status ${source.processing_status}`}>
                        {source.processing_status === "ready"
                          ? "Processed"
                          : source.processing_status === "uploaded"
                            ? "Ready to process"
                            : source.processing_status === "failed"
                              ? "Processing failed"
                              : "Processing"}
                      </span>
                      {results[source.id] && (
                        <div className="processing-details">
                          {results[source.id].page_count !== null && (
                            <span>
                              {results[source.id].page_count} pages ·{" "}
                            </span>
                          )}
                          {results[source.id].slide_count !== null && (
                            <span>
                              {results[source.id].slide_count} slides ·{" "}
                            </span>
                          )}
                          {results[source.id].duration_seconds !== null && (
                            <span>
                              {results[source.id].duration_seconds?.toFixed(1)}{" "}
                              seconds ·{" "}
                            </span>
                          )}
                          <span>
                            {results[source.id].text_evidence_count} text
                            evidence units
                          </span>
                          {results[source.id].warnings.map((warning, i) => (
                            <p key={i}>{warning}</p>
                          ))}
                        </div>
                      )}
                    </div>
                    {source.processing_status !== "ready" && (
                      <Button
                        className="secondary small"
                        busy={process.busy && processing === source.id}
                        disabled={
                          process.busy ||
                          source.processing_status === "processing"
                        }
                        onClick={() => void processSource(source)}
                      >
                        {source.processing_status === "failed"
                          ? "Retry processing"
                          : source.processing_status === "processing"
                            ? "Processing…"
                            : "Process"}
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="library-empty">
                <p>No sources yet.</p>
                <small>
                  Your uploaded material will appear here with its actual
                  processing status.
                </small>
              </div>
            ))}
        </section>
        <aside className="context-stack">
          <section className="card">
            <p className="eyebrow">From material to understanding</p>
            <h2>A foundation you can inspect.</h2>
            <ol className="guide-list">
              <li>
                <span>01</span>
                <div>
                  <strong>Add a source</strong>
                  <p>Your documents and lecture videos.</p>
                </div>
              </li>
              <li>
                <span>02</span>
                <div>
                  <strong>Process & index</strong>
                  <p>Extract evidence, then make it searchable.</p>
                </div>
              </li>
              <li>
                <span>03</span>
                <div>
                  <strong>Follow the evidence</strong>
                  <p>Ask, practice, and debug your reasoning.</p>
                </div>
              </li>
            </ol>
          </section>
          <section className="card indexing">
            <p className="eyebrow">Prepare for discovery</p>
            <h3>Make your sources searchable.</h3>
            <p>
              Index processed material before asking questions or generating
              practice.
            </p>
            <Button
              className="secondary full"
              busy={index.busy}
              disabled={
                !query.data?.some(
                  (source) => source.processing_status === "ready",
                )
              }
              onClick={() => void indexSources()}
            >
              Index course material <ArrowRight size={16} />
            </Button>
            <ErrorNotice error={index.error} />
            {indexed && (
              <p role="status" className="index-result">
                {indexed.searchable_evidence} searchable evidence units ·{" "}
                {indexed.embedded_count} newly indexed.
              </p>
            )}
          </section>
        </aside>
      </div>
      <div className="journey-callout">
        <div>
          <p className="eyebrow">Your material, put to work</p>
          <h3>Ask a question. See exactly where the answer comes from.</h3>
        </div>
        <Link to="/ask" className="button">
          Explore with Ask <ArrowRight size={16} />
        </Link>
      </div>
    </>
  );
}
