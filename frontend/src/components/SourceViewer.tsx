import { useCallback, useEffect, useRef, useState } from 'react';
import { api, assetURL } from '../api/client';
import type { Citation, VisualEvidence } from '../api/types';
import { useQuery, useTask } from '../hooks';
import { Button, ErrorNotice, Loading } from './ui';

export function SourceViewer({ citation, onClose }: { citation: Citation; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [assetFailed, setAssetFailed] = useState(false);
  useEffect(() => { const previous = document.activeElement; dialog.current?.showModal(); return () => { if (previous instanceof HTMLElement) previous.focus(); }; }, []);
  const location = useQuery(useCallback((signal: AbortSignal) => {
    const l = citation.locator;
    const query = citation.source_type === 'pdf' ? `kind=page&number=${l.page_number}` : citation.source_type === 'pptx' ? `kind=slide&number=${l.slide_number}` : `kind=time&start=${l.start_seconds ?? l.timestamp_seconds ?? 0}${l.end_seconds === undefined ? '' : `&end=${l.end_seconds}`}`;
    return api.location(citation.course_id, citation.source_version_id, query, signal);
  }, [citation]));
  const visual = useQuery(useCallback((signal: AbortSignal) => api.visual(citation.course_id, citation.evidence_unit_id, signal), [citation]));
  return <dialog className="source-dialog" ref={dialog} onCancel={onClose} onClose={onClose} aria-labelledby="source-title">
    <header className="section-heading"><div><h2 id="source-title">{citation.source_filename}</h2><p>{citation.locator_label} · {citation.modality} evidence</p></div><Button onClick={onClose}>Close source</Button></header>
    {location.loading && <Loading label="Opening exact source location…" />}<ErrorNotice error={location.error} retry={location.reload}/>
    {location.data && <>
      {location.data.preview_url ? <img className="source-preview" onError={() => setAssetFailed(true)} src={assetURL(location.data.preview_url)} alt={`${citation.source_filename}, ${citation.locator_label}`} /> : <video controls onError={() => setAssetFailed(true)} preload="metadata" src={assetURL(location.data.file_url)} onLoadedMetadata={event => { event.currentTarget.currentTime = location.data!.locator.start ?? 0; }} aria-label={`${citation.source_filename}, ${citation.locator_label}`} />}
      {assetFailed && <p role="alert">The source preview could not be loaded. Open the original source or try again.</p>}
      {location.data.preview_note && <p className="quiet-note">{location.data.preview_note}</p>}
      <a href={assetURL(location.data.file_url)} target="_blank" rel="noreferrer">Open original source</a>
    </>}
    <ErrorNotice error={visual.error} />{visual.data && <VisualDetail evidence={visual.data} />}
  </dialog>;
}
export function VisualDetail({ evidence }: { evidence: VisualEvidence }) {
  const [updated, setUpdated] = useState<VisualEvidence>();
  const task = useTask(); const value = updated ?? evidence;
  return <section className="visual-evidence"><h3>{value.evidence_type.replaceAll('_',' ')} evidence</h3>
    <p>{value.asset_extracted ? `Visual asset extracted · ${value.semantic_state === 'verified' ? 'Visual semantics independently verified' : 'Visual semantics not verified'}` : value.table_rows ? 'Structured table extracted from this source.' : 'Text extracted from this source.'}</p>
    {value.asset_url && <img className="source-preview" src={assetURL(value.asset_url)} alt="Extracted source visual" />}
    {value.semantic_description && <p>{value.semantic_description}</p>}
    {value.table_rows ? <div className="table-scroll"><table><tbody>{value.table_rows.map((row,i)=><tr key={i}>{row.map((cell,j)=><td key={j}>{cell}</td>)}</tr>)}</tbody></table></div> : value.text && <p className="prose">{value.text}</p>}
    {value.asset_extracted && value.semantic_state !== 'verified' && <Button busy={task.busy} onClick={async () => { const result = await task.run(signal=>api.interpret(value.citation.course_id,value.evidence_unit_id,signal)); if(result) setUpdated(result); }}>Interpret and verify visual</Button>}
    {updated?.semantic_state === 'verified' && <p>Re-index this course in Workspace to include the verified description in retrieval.</p>}
    <ErrorNotice error={task.error}/>
  </section>;
}

export function SourceInventory({course,source}: {course: string; source: string}) {
  const [open,setOpen]=useState(false);
  return <div><Button className="small secondary" onClick={()=>setOpen(!open)}>{open?'Hide evidence':'Inspect source evidence'}</Button>{open && <Inventory course={course} source={source}/>}</div>;
}
function Inventory({course,source}: {course:string;source:string}) {
  const query=useQuery(useCallback((signal:AbortSignal)=>api.sourceEvidence(course,source,signal),[course,source]));
  const [citation,setCitation]=useState<Citation>();
  return <div>{query.loading && <Loading label="Reading source evidence…"/>}<ErrorNotice error={query.error} retry={query.reload}/>{query.data?.map(e=><p key={e.evidence_unit_id}><Button className="small secondary" onClick={()=>setCitation(e.citation)}>{e.evidence_type} · {e.citation.locator_label}</Button></p>)}{query.data?.length===0 && <p>No extracted evidence yet. Process this source first.</p>}{citation && <SourceViewer citation={citation} onClose={()=>setCitation(undefined)}/>}</div>;
}
