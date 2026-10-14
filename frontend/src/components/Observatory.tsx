import { useEffect, useRef, useState } from "react";
import { ArrowRight, ArrowUpRight, BookOpen, GitBranch, Pause, Play, ScanLine } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { saveStorage } from "../state";

/** Decorative, code-rendered optics; never represents learner evidence. */
export function ObservatoryOptics() {
  return <svg className="observatory-optics" viewBox="0 0 800 680" fill="none" aria-hidden="true">
    <defs>
      <radialGradient id="orb-body" cx=".34" cy=".23" r=".8">
        <stop stopColor="#fffef0" stopOpacity=".98"/><stop offset=".17" stopColor="#e9e9d8" stopOpacity=".87"/>
        <stop offset=".43" stopColor="#b4c4bd" stopOpacity=".55"/><stop offset=".7" stopColor="#799591" stopOpacity=".3"/>
        <stop offset=".88" stopColor="#e6e8d2" stopOpacity=".87"/><stop offset="1" stopColor="#f4f0d8" stopOpacity=".96"/>
      </radialGradient>
      <radialGradient id="orb-depth" cx=".68" cy=".7" r=".65"><stop stopColor="#e7e1c1" stopOpacity=".55"/><stop offset=".45" stopColor="#d2dcd0" stopOpacity=".03"/><stop offset=".85" stopColor="#dceadd" stopOpacity=".3"/><stop offset="1" stopColor="#f7f8e7" stopOpacity=".8"/></radialGradient>
      <linearGradient id="orbit-metal" x1="100" y1="200" x2="680" y2="490" gradientUnits="userSpaceOnUse"><stop stopColor="#efdbc0"/><stop offset=".22" stopColor="#a77c54"/><stop offset=".48" stopColor="#e9eee2"/><stop offset=".72" stopColor="#b0845a"/><stop offset="1" stopColor="#eee7d8"/></linearGradient>
      <linearGradient id="glass-edge" x1="200" y1="120" x2="600" y2="510" gradientUnits="userSpaceOnUse"><stop stopColor="#d7ece3" stopOpacity=".05"/><stop offset=".43" stopColor="#d4f0e9" stopOpacity=".85"/><stop offset=".65" stopColor="#658c8b" stopOpacity=".2"/><stop offset="1" stopColor="#ddf7e7" stopOpacity=".9"/></linearGradient>
      <linearGradient id="window-light" x1="320" y1="170" x2="530" y2="400" gradientUnits="userSpaceOnUse"><stop stopColor="#fff" stopOpacity=".7"/><stop offset="1" stopColor="#fff" stopOpacity="0"/></linearGradient>
      <radialGradient id="flare"><stop stopColor="#fffef1"/><stop offset=".13" stopColor="#fffad5" stopOpacity=".85"/><stop offset="1" stopColor="#eef5d7" stopOpacity="0"/></radialGradient>
      <filter id="soft-glow"><feGaussianBlur stdDeviation="12"/></filter>
      <filter id="blur-reflection"><feGaussianBlur stdDeviation="3"/></filter>
      <clipPath id="sphere-clip"><circle cx="402" cy="324" r="151"/></clipPath>
    </defs>
    <ellipse cx="413" cy="570" rx="209" ry="22" fill="#091d20" opacity=".7" filter="url(#soft-glow)"/>
    <g className="orbit-back">
      <ellipse cx="399" cy="335" rx="299" ry="88" transform="rotate(17 399 335)" stroke="url(#orbit-metal)" strokeWidth="3"/>
      <ellipse cx="399" cy="335" rx="281" ry="78" transform="rotate(17 399 335)" stroke="#afccc7" strokeOpacity=".35"/>
      <ellipse cx="402" cy="332" rx="220" ry="181" transform="rotate(-34 402 332)" stroke="url(#glass-edge)" strokeWidth="2"/>
      <ellipse cx="402" cy="332" rx="216" ry="178" transform="rotate(-34 402 332)" stroke="#d4eee3" strokeOpacity=".25"/>
      <ellipse cx="402" cy="332" rx="110" ry="221" transform="rotate(35 402 332)" stroke="url(#orbit-metal)" strokeWidth="1.2" opacity=".65"/>
    </g>
    <g className="sphere-material">
      <circle cx="402" cy="324" r="154" fill="#e8f1da" opacity=".12" filter="url(#soft-glow)"/>
      <circle cx="402" cy="324" r="151" fill="url(#orb-body)" stroke="#edf2df" strokeWidth="1.5"/>
      <circle cx="402" cy="324" r="145" fill="url(#orb-depth)" stroke="#f3f0de" strokeOpacity=".35"/>
      <g clipPath="url(#sphere-clip)">
        <path d="M432 169 Q533 187 546 310 L493 353 Q509 224 419 195Z" fill="url(#window-light)"/>
        <path d="M461 192 Q519 220 523 278 L494 294 Q490 228 452 206Z" fill="#fffef3" opacity=".58"/>
        <path d="M279 274 Q280 199 369 181 Q316 229 316 288Z" fill="#fffce7" opacity=".18"/>
        <path d="M257 358 Q365 422 552 312 L563 359 Q401 452 258 394Z" fill="#e6ead5" opacity=".22" filter="url(#blur-reflection)"/>
        <path d="M277 414 Q399 480 531 399" stroke="#fff4d5" strokeWidth="8" opacity=".3" filter="url(#blur-reflection)"/>
        <path d="M293 250 Q261 344 310 407" stroke="#f5f7e8" strokeWidth="3" opacity=".45"/>
        <ellipse cx="393" cy="433" rx="110" ry="20" stroke="#ffffed" strokeOpacity=".23" transform="rotate(-13 393 433)"/>
      </g>
      <circle cx="438" cy="220" r="27" fill="url(#flare)"/>
      <circle cx="317" cy="383" r="14" fill="url(#flare)"/>
    </g>
    <g className="orbit-front">
      <path d="M119 257 C19 326 656 515 690 417 C703 383 647 350 592 326" stroke="url(#orbit-metal)" strokeWidth="2.8"/>
      <path d="M244 492 C195 446 462 292 608 291" stroke="url(#glass-edge)" strokeWidth="2"/>
      <path d="M261 509 C211 468 446 310 609 306" stroke="#b2dbd3" strokeOpacity=".42"/>
      <path d="M228 264 C151 404 386 598 558 456" stroke="url(#glass-edge)" strokeWidth="2"/>
      <circle cx="556" cy="222" r="25" fill="url(#flare)"/>
      <circle cx="269" cy="486" r="16" fill="url(#flare)"/>
      <circle cx="619" cy="452" r="4" fill="#e9d8bc"/>
    </g>
  </svg>;
}

export function Observatory() {
  const navigate = useNavigate();
  useEffect(() => { document.title = "ConceptLens — Concept Observatory"; }, []);
  const scene = useRef<HTMLDivElement>(null);
  const [paused, setPaused] = useState(false);
  const enter = (path = "/learn") => {
    saveStorage("conceptlens:intro-seen", "yes");
    navigate(path);
  };
  return <div className={`observatory ${paused ? "motion-paused" : ""}`}>
    <header className="observatory-nav">
      <Link className="brand" to="/?intro=1"><span className="lens-logo" aria-hidden="true"/><span>Concept<span className="brand-light">Lens</span></span></Link>
      <nav aria-label="Explore ConceptLens">{["Workspace", "Ask", "Learn", "Practice", "Dashboard"].map(label => <Link key={label} to={`/${label.toLowerCase()}`} onClick={() => saveStorage("conceptlens:intro-seen", "yes")}>{label}</Link>)}</nav>
      <button className="intro-skip" onClick={() => enter("/workspace")}>Skip intro <ArrowUpRight size={15}/></button>
    </header>
    <main className="observatory-hero">
      <div className="architecture" aria-hidden="true"><div className="arch-window"/><div className="light-shaft"/><div className="architecture-step step-one"/><div className="architecture-step step-two"/><div className="architecture-plinth"/></div>
      <div className="hero-copy">
        <p className="eyebrow"><span/> Clarity through connections</p>
        <h1>See how<br/>ideas connect.</h1>
        <p className="hero-tagline">Learn anything. Debug your understanding.</p>
        <p className="hero-description">Build understanding by connecting ideas,<br className="desktop-break"/> checking your reasoning, and discovering<br className="desktop-break"/> what to explore next.</p>
        <div className="hero-actions"><button className="button" onClick={() => enter()}>Start learning <ArrowRight size={17}/></button><a href="#the-approach" className="approach-link">Explore the approach <span><ArrowRight size={14}/></span></a></div>
        <div className="hero-footnote"><span/> Your material. A more connected understanding.</div>
      </div>
      <div className="optics-scene" ref={scene} onPointerMove={event => {
        if (event.pointerType !== "mouse" || window.matchMedia("(prefers-reduced-motion: reduce)").matches || paused) return;
        const bounds = event.currentTarget.getBoundingClientRect();
        scene.current?.style.setProperty("--pointer-x", `${(event.clientX - bounds.x - bounds.width / 2) / 55}px`);
        scene.current?.style.setProperty("--pointer-y", `${(event.clientY - bounds.y - bounds.height / 2) / 65}px`);
      }} onPointerLeave={() => { scene.current?.style.setProperty("--pointer-x", "0px"); scene.current?.style.setProperty("--pointer-y", "0px"); }}>
        <div className="optics-depth"><ObservatoryOptics/>
          <button className="glass-concept glass-prerequisite" onClick={() => enter("/dashboard")}><span className="glass-number">01 / FOUNDATIONS</span><strong>Prerequisite<br/>concepts</strong><div className="molecule" aria-hidden="true"><i/><i/><i/><i/></div><small>See what builds<br/>this idea.</small><ArrowUpRight size={17}/></button>
          <button className="glass-concept glass-related" onClick={() => enter("/learn")}><span className="glass-number">02 / CONNECTIONS</span><strong>Related ideas</strong><GitBranch className="glass-symbol" size={39} strokeWidth={1}/><small>Explore the<br/>connections.</small><ArrowUpRight size={17}/></button>
          <button className="glass-concept glass-application" onClick={() => enter("/practice")}><span className="glass-number">03 / UNDERSTANDING</span><strong>Put ideas<br/>into practice</strong><div className="glass-torus" aria-hidden="true"/><small>See the<br/>bigger picture.</small><ArrowUpRight size={17}/></button>
        </div>
      </div>
      <div className="hero-bottom"><span>THE CONCEPT OBSERVATORY</span><span className="hero-coordinate">Ideas / Context / Reasoning / Connections</span><button className="motion-toggle" aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? <Play size={13}/> : <Pause size={13}/>} {paused ? "Resume motion" : "Pause motion"}</button></div>
    </main>
    <section className="observatory-approach" id="the-approach">
      <div className="approach-heading"><p className="eyebrow">From curiosity to clarity</p><h2>A space to see the whole idea.</h2><p>Bring your sources. Follow the connections. Make the understanding yours.</p></div>
      <div className="approach-cards">{[
        { icon: BookOpen, label: "Grounded in your material", text: "Every answer starts with your course sources, with evidence you can inspect.", path: "/workspace" },
        { icon: ScanLine, label: "Built around your reasoning", text: "Make your thinking visible. Find the turning point and take a better next step.", path: "/learn" },
        { icon: GitBranch, label: "Connected by evidence", text: "Explore recorded relationships and check understanding through fresh practice.", path: "/dashboard" },
      ].map(({icon:Icon,label,text,path},i) => <button key={path} onClick={() => enter(path)}><span className="approach-index">0{i+1}</span><Icon size={26} strokeWidth={1.3}/><h3>{label}</h3><p>{text}</p><ArrowUpRight size={18}/></button>)}</div>
      <footer><span>ConceptLens / Concept Observatory</span><span>Grounded in your material. Guided by evidence.</span></footer>
    </section>
  </div>;
}
