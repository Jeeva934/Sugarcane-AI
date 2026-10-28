import { FormEvent, ReactNode, useEffect, useState } from "react";
import {
  Activity, ArrowRight, BadgeAlert, BookOpen, Check, ChevronDown, CircleHelp, CloudSun,
  Globe2, History, Leaf, LogOut, MapPin, Menu, Plus, Settings, ShieldCheck, Sprout, Upload, X,
} from "lucide-react";
import { api, DiagnosisHistory, Farm, Knowledge, ModelVersion, RiskHistory, User } from "./api";

type Language = "en" | "ta";
type View = "overview" | "diagnosis" | "risk" | "farms" | "history" | "knowledge" | "settings" | "admin";
type DiagnosisResult = {
  status: string;
  predicted_class: string;
  uncalibrated_score: number;
  alternative_predictions: { disease_class: string; uncalibrated_score: number }[];
  model_version: string;
  processing_time_ms: number;
  warning: string;
  saved_to_history: boolean;
};

const copy = {
  en: {
    eyebrow: "FIELD-READY DECISION SUPPORT", title: "Healthier fields start with a clearer picture.",
    intro: "Understand what your observations can—and cannot—tell you about sugarcane disease.",
    diagnose: "Diagnose a leaf", risk: "Check disease risk", overview: "Overview", farms: "My farms",
    diagnosis: "Leaf diagnosis", riskNav: "Disease risk", welcome: "Good day", subtitle: "Your field monitoring workspace",
    honest: "Models not configured", honestBody: "This project has no validated disease models yet. It will not invent diagnoses or risk scores.",
    action: "Set up your farm to get started", addFarm: "Add a farm", farmName: "Farm name", location: "Location coordinates (optional)",
    latitude: "Latitude", longitude: "Longitude", crop: "Crop variety (optional)", saveFarm: "Save farm",
    cancel: "Cancel", noFarms: "No farms added yet", noFarmsBody: "Add a farm to organize observations and future assessments.",
    modules: "Two independent assessment modules", environmental: "Environmental risk", environmentalBody: "A validated weather-linked risk model is not configured. No current risk estimate is available.",
    visual: "Image diagnosis", visualBody: "Upload support is ready, but a validated image classifier is not installed. No diagnosis will be returned.",
    transparent: "Designed to be transparent", transparentBody: "Explanations describe how a model arrived at an output; they do not prove biological causation. The environmental and image modules are separate—not a jointly trained classifier.",
    chooseImage: "Choose a leaf image", imageHelp: "JPEG, PNG or WebP up to 10 MB. Avoid blurry or poorly lit images.",
    upload: "Select image", send: "Submit for diagnosis", uploadNone: "No image selected", modelUnavailable: "Diagnosis unavailable: a validated image model is not configured.",
    experimentalModel: "Experimental image model enabled", experimentalWarning: "This model is not independently field-validated. Its score is uncalibrated and is not a confirmed diagnosis.",
    outputScore: "Uncalibrated model score", alternatives: "Other model outputs", resultLabel: "Experimental model output",
    selectFarm: "Select a farm", selectDisease: "Disease class", riskUnavailable: "Risk assessment unavailable: a validated risk model and observed weather data are required.",
    riskNote: "A weather summary is not a disease probability. Missing or stale data will never be replaced with invented values.",
    signIn: "Sign in", signUp: "Create account", email: "Email", password: "Password (12+ characters)", name: "Full name",
    logout: "Sign out", session: "Sign in to save farms and view your workspace.", login: "Continue", register: "Create account",
    source: "Academic decision-support prototype", limitation: "Not a substitute for expert agricultural advice.",
    locationUnknown: "Location not set", varietyUnknown: "Variety not recorded", language: "Language",
    knowledge: "Reviewed knowledge base", noKnowledge: "No reviewed knowledge entries are available yet.",
    failed: "Something went wrong", admin: "Admin area", offline: "Offline inference unavailable",
  },
  ta: {
    eyebrow: "வயல் முடிவு ஆதரவு", title: "தெளிவான பார்வையுடன் ஆரோக்கியமான வயல்கள் தொடங்குகின்றன.",
    intro: "கரும்பு நோய் குறித்து உங்கள் கண்காணிப்புகள் என்ன தெரிவிக்க முடியும், முடியாது என்பதை அறியுங்கள்.",
    diagnose: "இலையை பரிசோதிக்கவும்", risk: "நோய் அபாயத்தைப் பார்க்கவும்", overview: "மேலோட்டம்", farms: "எனது பண்ணைகள்",
    diagnosis: "இலை பரிசோதனை", riskNav: "நோய் அபாயம்", welcome: "வணக்கம்", subtitle: "உங்கள் வயல் கண்காணிப்பு பணியிடம்",
    honest: "மாதிரிகள் அமைக்கப்படவில்லை", honestBody: "இந்த திட்டத்தில் சரிபார்க்கப்பட்ட நோய் மாதிரிகள் இல்லை. உருவாக்கப்பட்ட நோயறிதல் அல்லது அபாய மதிப்பெண்கள் காட்டப்படாது.",
    action: "தொடங்க உங்கள் பண்ணையைச் சேர்க்கவும்", addFarm: "பண்ணை சேர்க்கவும்", farmName: "பண்ணையின் பெயர்", location: "இருப்பிட ஒருங்கிணைப்புகள் (விருப்பம்)",
    latitude: "அட்சரேகை", longitude: "தீர்க்கரேகை", crop: "கரும்பு வகை (விருப்பம்)", saveFarm: "பண்ணையைச் சேமிக்கவும்",
    cancel: "ரத்து", noFarms: "இன்னும் பண்ணைகள் சேர்க்கப்படவில்லை", noFarmsBody: "கண்காணிப்புகள் மற்றும் மதிப்பீடுகளை ஒழுங்குபடுத்த பண்ணையைச் சேர்க்கவும்.",
    modules: "இரண்டு தனித்த மதிப்பீட்டு தொகுதிகள்", environmental: "சுற்றுச்சூழல் அபாயம்", environmentalBody: "சரிபார்க்கப்பட்ட வானிலை சார்ந்த அபாய மாதிரி அமைக்கப்படவில்லை. தற்போதைய அபாய மதிப்பீடு இல்லை.",
    visual: "பட அடிப்படையிலான நோயறிதல்", visualBody: "பட பதிவேற்றம் உள்ளது; சரிபார்க்கப்பட்ட பட வகைப்படுத்தி நிறுவப்படவில்லை. நோயறிதல் வழங்கப்படாது.",
    transparent: "வெளிப்படைத்தன்மைக்காக வடிவமைக்கப்பட்டது", transparentBody: "விளக்கங்கள் மாதிரி முடிவை எவ்வாறு உருவாக்கியது என்பதைக் காட்டும்; உயிரியல் காரணத்தை நிரூபிக்காது. இந்த இரண்டு தொகுதிகளும் தனித்தனியானவை.",
    chooseImage: "இலைப் படத்தைத் தேர்ந்தெடுக்கவும்", imageHelp: "10 MB வரை JPEG, PNG அல்லது WebP. மங்கலான அல்லது குறைந்த ஒளி படங்களைத் தவிர்க்கவும்.",
    upload: "படத்தைத் தேர்ந்தெடுக்கவும்", send: "நோயறிதலுக்குச் சமர்ப்பிக்கவும்", uploadNone: "படம் தேர்ந்தெடுக்கப்படவில்லை", modelUnavailable: "சரிபார்க்கப்பட்ட பட மாதிரி அமைக்கப்படாததால் நோயறிதல் கிடைக்காது.",
    experimentalModel: "சோதனைப் பட மாதிரி செயல்படுத்தப்பட்டுள்ளது", experimentalWarning: "இந்த மாதிரி தனித்த வயல் ஆய்வில் சரிபார்க்கப்படவில்லை. மதிப்பெண் அளவீடு செய்யப்படாதது; உறுதியான நோயறிதல் அல்ல.",
    outputScore: "அளவீடு செய்யப்படாத மாதிரி மதிப்பெண்", alternatives: "மற்ற மாதிரி வெளியீடுகள்", resultLabel: "சோதனை மாதிரி வெளியீடு",
    selectFarm: "பண்ணையைத் தேர்ந்தெடுக்கவும்", selectDisease: "நோய் வகை", riskUnavailable: "சரிபார்க்கப்பட்ட அபாய மாதிரியும் வானிலைத் தரவும் தேவை.",
    riskNote: "வானிலை சுருக்கம் நோய் நிகழ்தகவு அல்ல. இல்லாத அல்லது பழைய தரவு உருவாக்கப்படாது.",
    signIn: "உள்நுழைக", signUp: "கணக்கை உருவாக்கவும்", email: "மின்னஞ்சல்", password: "கடவுச்சொல் (12+ எழுத்துகள்)", name: "முழுப் பெயர்",
    logout: "வெளியேறு", session: "பண்ணைகளைச் சேமிக்கவும் பணியிடத்தைக் காணவும் உள்நுழைக.", login: "தொடரவும்", register: "கணக்கை உருவாக்கவும்",
    source: "கல்விசார் முடிவு ஆதரவு முன்மாதிரி", limitation: "வேளாண் நிபுணர் ஆலோசனைக்கு மாற்றாகாது.",
    locationUnknown: "இருப்பிடம் அமைக்கப்படவில்லை", varietyUnknown: "வகை பதிவு செய்யப்படவில்லை", language: "மொழி",
    knowledge: "மதிப்பாய்வு செய்யப்பட்ட அறிவுத் தளம்", noKnowledge: "மதிப்பாய்வு செய்யப்பட்ட அறிவுப் பதிவுகள் இல்லை.",
    failed: "பிழை ஏற்பட்டது", admin: "நிர்வாகம்", offline: "இணையமற்ற கணிப்பு கிடைக்காது",
  },
} satisfies Record<Language, Record<string, string>>;

export default function App() {
  const [language, setLanguage] = useState<Language>("en");
  const [view, setView] = useState<View>("overview");
  const [user, setUser] = useState<User | null>(null);
  const [farms, setFarms] = useState<Farm[]>([]);
  const [loading, setLoading] = useState(true);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [farmOpen, setFarmOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [mobileMenu, setMobileMenu] = useState(false);
  const t = copy[language];

  async function loadWorkspace() {
    try {
      const current = await api<User>("/auth/me");
      setUser(current);
      setLanguage(current.preferred_language);
      setFarms(await api<Farm[]>("/farms"));
    } catch {
      setUser(null);
      setFarms([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadWorkspace(); }, []);

  async function signOut() {
    await api<void>("/auth/logout", { method: "POST" });
    setUser(null);
    setFarms([]);
  }

  const navigate = (next: View) => {
    setView(next);
    setMobileMenu(false);
    setNotice("");
    if (!user && next !== "overview") setAuthOpen(true);
  };
  async function changeLanguage(next: Language) {
    setLanguage(next);
    if (user) {
      try {
        const updated = await api<User>("/auth/me", { method: "PATCH", body: JSON.stringify({ preferred_language: next }) });
        setUser(updated);
      } catch {
        setNotice("Language preference could not be saved.");
      }
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => navigate("overview")} aria-label="Sugarcane AI home">
          <span className="brand-mark"><Sprout size={22} /></span>
          <span><strong>Sugarcane AI</strong><small>FIELD HEALTH, MADE CLEARER</small></span>
        </button>
        <button className="mobile-toggle" onClick={() => setMobileMenu(!mobileMenu)} aria-label="Toggle navigation">{mobileMenu ? <X /> : <Menu />}</button>
        <div className={`topbar-actions ${mobileMenu ? "open" : ""}`}>
          <label className="language-picker"><Globe2 size={16} /><span className="sr-only">{t.language}</span>
            <select aria-label={t.language} value={language} onChange={(event) => void changeLanguage(event.target.value as Language)}>
              <option value="en">English</option><option value="ta">தமிழ்</option>
            </select><ChevronDown size={13} />
          </label>
          {user ? <><span className="user-name">{user.full_name}</span><button className="quiet-button" onClick={() => void signOut()}><LogOut size={15} />{t.logout}</button></>
            : <button className="quiet-button" onClick={() => setAuthOpen(true)}>{t.signIn}</button>}
        </div>
      </header>
      <main className="layout">
        <aside className={`sidebar ${mobileMenu ? "open" : ""}`}>
          <p className="nav-heading">WORKSPACE</p>
          <NavButton active={view === "overview"} onClick={() => navigate("overview")} icon={<Activity size={17} />}>{t.overview}</NavButton>
          <NavButton active={view === "diagnosis"} onClick={() => navigate("diagnosis")} icon={<Leaf size={17} />}>{t.diagnosis}</NavButton>
          <NavButton active={view === "risk"} onClick={() => navigate("risk")} icon={<CloudSun size={17} />}>{t.riskNav}</NavButton>
          <NavButton active={view === "farms"} onClick={() => navigate("farms")} icon={<MapPin size={17} />}>{t.farms}</NavButton>
          <NavButton active={view === "history"} onClick={() => navigate("history")} icon={<History size={17} />}>History</NavButton>
          <NavButton active={view === "knowledge"} onClick={() => navigate("knowledge")} icon={<BookOpen size={17} />}>Knowledge</NavButton>
          <NavButton active={view === "settings"} onClick={() => navigate("settings")} icon={<Settings size={17} />}>Settings</NavButton>
          {user?.role === "admin" && <NavButton active={view === "admin"} onClick={() => navigate("admin")} icon={<ShieldCheck size={17} />}>Admin</NavButton>}
          <div className="sidebar-bottom"><span className="online-dot" /> API connection <span className="offline-label">{t.offline}</span></div>
        </aside>
        <section className="content">
          {loading ? <div className="loading-panel" role="status">Loading your workspace…</div> : null}
          {!loading && !user ? <GuestLanding t={t} onAuth={() => setAuthOpen(true)} onNavigate={navigate} /> : null}
          {!loading && user && view === "overview" ? <Overview user={user} farms={farms} t={t} onFarm={() => setFarmOpen(true)} onNavigate={navigate} /> : null}
          {!loading && user && view === "farms" ? <FarmList farms={farms} t={t} onFarm={() => setFarmOpen(true)} /> : null}
          {!loading && user && view === "diagnosis" ? <Diagnosis farms={farms} t={t} /> : null}
          {!loading && user && view === "risk" ? <RiskAssessment farms={farms} t={t} /> : null}
          {!loading && user && view === "history" ? <HistoryView t={t} /> : null}
          {!loading && user && view === "knowledge" ? <KnowledgeView language={language} /> : null}
          {!loading && user && view === "settings" ? <SettingsView user={user} language={language} onLanguage={changeLanguage} onDeleted={async () => { await signOut(); setView("overview"); }} /> : null}
          {!loading && user && view === "admin" && user.role === "admin" ? <AdminView /> : null}
          <footer className="footer"><span>{t.source}</span><span>{t.limitation}</span></footer>
        </section>
      </main>
      {farmOpen && user && <FarmDialog t={t} onClose={() => setFarmOpen(false)} onSaved={(farm) => { setFarms((existing) => [farm, ...existing]); setFarmOpen(false); }} />}
      {authOpen && <AuthDialog t={t} mode={authMode} setMode={setAuthMode} onClose={() => setAuthOpen(false)} onSuccess={() => { setAuthOpen(false); void loadWorkspace(); }} />}
      {notice && <div role="status" className="toast"><Check size={17} />{notice}<button aria-label="Dismiss" onClick={() => setNotice("")}><X size={15} /></button></div>}
    </div>
  );
}

function NavButton({ active, onClick, icon, children }: { active: boolean; onClick: () => void; icon: ReactNode; children: ReactNode }) {
  return <button className={`nav-item ${active ? "active" : ""}`} onClick={onClick}>{icon}<span>{children}</span>{active && <span className="active-mark" />}</button>;
}

function GuestLanding({ t, onAuth, onNavigate }: { t: typeof copy.en; onAuth: () => void; onNavigate: (view: View) => void }) {
  return <div className="guest-page">
    <div className="hero">
      <div className="hero-copy"><span className="eyebrow"><Leaf size={14} />{t.eyebrow}</span>
        <h1>{t.title}</h1><p>{t.intro}</p>
        <div className="hero-actions"><button className="primary-button" onClick={() => onNavigate("diagnosis")}>{t.diagnose}<ArrowRight size={17} /></button><button className="secondary-button" onClick={() => onNavigate("risk")}>{t.risk}<ArrowRight size={17} /></button></div>
      </div>
      <div className="hero-art" aria-hidden="true"><div className="sun-disc" /><div className="field field-back" /><div className="field field-front" /><div className="leaf-illustration"><Leaf size={80} strokeWidth={1} /></div><div className="art-caption"><Sprout size={15} /> Crop health, with context</div></div>
    </div>
    <ModelStatus t={t} />
    <section className="section-block"><div className="section-title"><span className="eyebrow">HOW IT WORKS</span><h2>{t.modules}</h2></div>
      <div className="module-grid">
        <article className="module-card"><div className="module-icon"><CloudSun /></div><h3>{t.environmental}</h3><p>{t.environmentalBody}</p><span className="status-pill unavailable"><span />Not ready</span></article>
        <article className="module-card"><div className="module-icon"><Leaf /></div><h3>{t.visual}</h3><p>{t.visualBody}</p><span className="status-pill unavailable"><span />Not ready</span></article>
      </div>
    </section>
    <div className="explain-banner"><div className="shield-icon"><ShieldCheck /></div><div><h3>{t.transparent}</h3><p>{t.transparentBody}</p></div></div>
    <div className="sign-in-strip"><div><strong>Keep your observations in one place.</strong><p>Sign in to manage farms and access your monitoring workspace.</p></div><button className="secondary-button" onClick={onAuth}>{t.signIn}<ArrowRight size={16} /></button></div>
  </div>;
}

function Overview({ user, farms, t, onFarm, onNavigate }: { user: User; farms: Farm[]; t: typeof copy.en; onFarm: () => void; onNavigate: (view: View) => void }) {
  return <div className="page-enter">
    <div className="page-heading"><div><span className="eyebrow">FIELD DASHBOARD</span><h1>{t.welcome}, {user.full_name.split(" ")[0]}</h1><p>{t.subtitle}</p></div><button className="primary-button" onClick={onFarm}><Plus size={17} />{t.addFarm}</button></div>
    <ModelStatus t={t} />
    <div className="section-heading-row"><div><span className="eyebrow">YOUR FIELDS</span><h2>{t.action}</h2></div></div>
    {farms.length ? <div className="farm-grid">{farms.map((farm) => <FarmCard key={farm.id} farm={farm} t={t} />)}</div>
      : <div className="empty-card"><div className="empty-icon"><Sprout /></div><div><h3>{t.noFarms}</h3><p>{t.noFarmsBody}</p></div><button className="secondary-button" onClick={onFarm}>{t.addFarm}<ArrowRight size={16} /></button></div>}
    <div className="section-heading-row lower"><div><span className="eyebrow">QUICK ACTIONS</span><h2>Choose an assessment</h2></div></div>
    <div className="action-grid"><button className="action-card" onClick={() => onNavigate("diagnosis")}><span className="action-icon"><Leaf /></span><span><strong>{t.diagnose}</strong><small>Image-based module · model unavailable</small></span><ArrowRight size={18} /></button><button className="action-card" onClick={() => onNavigate("risk")}><span className="action-icon"><CloudSun /></span><span><strong>{t.risk}</strong><small>Weather-linked module · model unavailable</small></span><ArrowRight size={18} /></button></div>
  </div>;
}

function ModelStatus({ t }: { t: typeof copy.en }) {
  return <div className="model-banner"><div className="banner-symbol"><BadgeAlert size={20} /></div><div><strong>{t.honest}</strong><p>{t.honestBody}</p></div><span className="banner-tag">DEVELOPMENT</span></div>;
}

function FarmCard({ farm, t }: { farm: Farm; t: typeof copy.en }) {
  return <article className="farm-card"><div className="farm-card-top"><div className="farm-avatar"><Sprout /></div><span className="status-pill"><span />Monitoring</span></div><h3>{farm.name}</h3><p className="farm-detail"><MapPin size={15} />{farm.latitude !== null && farm.longitude !== null ? `${farm.latitude.toFixed(4)}, ${farm.longitude.toFixed(4)}` : t.locationUnknown}</p><p className="farm-detail"><Leaf size={15} />{farm.crop_variety || t.varietyUnknown}</p><div className="farm-card-foot"><span>No assessments yet</span><Activity size={15} /></div></article>;
}

function FarmList({ farms, t, onFarm }: { farms: Farm[]; t: typeof copy.en; onFarm: () => void }) {
  return <div className="page-enter"><div className="page-heading"><div><span className="eyebrow">FARM MANAGEMENT</span><h1>{t.farms}</h1><p>Locations you have added to your account.</p></div><button className="primary-button" onClick={onFarm}><Plus size={17} />{t.addFarm}</button></div>{farms.length ? <div className="farm-grid">{farms.map((farm) => <FarmCard key={farm.id} farm={farm} t={t} />)}</div> : <div className="empty-card"><Sprout /><div><h3>{t.noFarms}</h3><p>{t.noFarmsBody}</p></div></div>}</div>;
}

function Diagnosis({ farms, t }: { farms: Farm[]; t: typeof copy.en }) {
  const [file, setFile] = useState<File | null>(null);
  const [farmId, setFarmId] = useState("");
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [modelStatus, setModelStatus] = useState("checking");
  const [result, setResult] = useState<DiagnosisResult | null>(null);
  useEffect(() => { if (!file) { setPreview(""); return; } const url = URL.createObjectURL(file); setPreview(url); return () => URL.revokeObjectURL(url); }, [file]);
  useEffect(() => {
    void api<{ checks: { image_model?: string } }>("/health/ready")
      .then((health) => setModelStatus(health.checks.image_model ?? "unavailable"))
      .catch(() => setModelStatus("unavailable"));
  }, []);
  function choose(candidate?: File) {
    setError("");
    if (!candidate) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(candidate.type) || candidate.size > 10 * 1024 * 1024) { setError("Choose a JPEG, PNG or WebP image smaller than 10 MB."); return; }
    setFile(candidate);
    setResult(null);
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    const body = new FormData(); body.append("file", file);
    const query = farmId ? `?farm_id=${encodeURIComponent(farmId)}` : "";
    setSubmitting(true); setError("");
    try { setResult(await api<DiagnosisResult>(`/diagnosis/predict${query}`, { method: "POST", body })); }
    catch (e) { setError(e instanceof Error ? e.message : t.modelUnavailable); }
    finally { setSubmitting(false); }
  }
  return <div className="page-enter"><div className="page-heading"><div><span className="eyebrow">IMAGE-BASED MODULE</span><h1>{t.diagnosis}</h1><p>Capture a clear image of a sugarcane leaf to request an assessment.</p></div></div><div className="model-notice"><BadgeAlert size={18} /><div><strong>{modelStatus === "experimental_enabled" ? t.experimentalModel : t.modelUnavailable}</strong><p>{modelStatus === "experimental_enabled" ? t.experimentalWarning : "Model status is reported honestly; no placeholder or simulated result will be displayed."}</p></div></div><form className="diagnosis-form" onSubmit={(e) => void submit(e)}><label className="field-label">{t.chooseImage}</label><p className="field-hint">{t.imageHelp}</p>{preview ? <div className="image-preview"><img src={preview} alt="Selected leaf preview" /><button type="button" className="remove-image" onClick={() => { setFile(null); setResult(null); }} aria-label="Remove image"><X size={16} /></button></div> : <label className="drop-zone"><Upload size={24} /><strong>{t.upload}</strong><span>{t.uploadNone}</span><input type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={(e) => choose(e.target.files?.[0])} /></label>}<label className="field-label" htmlFor="diagnosis-farm">{t.selectFarm}</label><select id="diagnosis-farm" className="text-input" value={farmId} onChange={(e) => setFarmId(e.target.value)}><option value="">No farm selected</option>{farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select>{error && <p className="form-error" role="alert">{error}</p>}{result && <section className="prediction-result" aria-live="polite"><span className="eyebrow">{t.resultLabel}</span><h3>{result.predicted_class}</h3><p>{t.outputScore}: <strong>{result.uncalibrated_score.toFixed(3)}</strong></p><p className="field-hint">Model {result.model_version} · {result.processing_time_ms} ms · saved to history without the uploaded image</p><p className="result-warning">{result.warning}</p><details><summary>{t.alternatives}</summary>{result.alternative_predictions.map((item) => <p key={item.disease_class}>{item.disease_class}: {item.uncalibrated_score.toFixed(3)}</p>)}</details></section>}<button className="primary-button submit-button" disabled={!file || submitting}>{submitting ? "Checking…" : t.send}<ArrowRight size={17} /></button></form></div>;
}

function RiskAssessment({ farms, t }: { farms: Farm[]; t: typeof copy.en }) {
  const [farmId, setFarmId] = useState("");
  const [disease, setDisease] = useState("");
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault(); setError("");
    try { await api("/risk/predict", { method: "POST", body: JSON.stringify({ farm_id: farmId, disease_class: disease, period_start: new Date(Date.now() - 7 * 86400000).toISOString(), period_end: new Date().toISOString() }) }); }
    catch (e) { setError(e instanceof Error ? e.message : t.riskUnavailable); }
  }
  return <div className="page-enter"><div className="page-heading"><div><span className="eyebrow">ENVIRONMENTAL MODULE</span><h1>{t.riskNav}</h1><p>Risk estimation requires current observations and a validated model.</p></div></div><div className="model-notice"><CloudSun size={19} /><div><strong>{t.riskUnavailable}</strong><p>{t.riskNote}</p></div></div><form className="assessment-form" onSubmit={(e) => void submit(e)}><label className="field-label" htmlFor="risk-farm">{t.selectFarm}</label><select id="risk-farm" className="text-input" value={farmId} onChange={(e) => setFarmId(e.target.value)} required><option value="">Choose a farm</option>{farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}</select><label className="field-label" htmlFor="risk-disease">{t.selectDisease}</label><input id="risk-disease" className="text-input" value={disease} onChange={(e) => setDisease(e.target.value)} placeholder="Disease class supported by your model" required /><p className="field-hint">Only use a disease class listed in the active model metadata.</p>{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button submit-button" disabled={!farms.length}>{t.risk}<ArrowRight size={17} /></button></form><div className="explain-banner compact"><CircleHelp /><div><h3>Independent outputs, not a combined diagnosis</h3><p>An environmental risk indicator cannot confirm disease. Image analysis, when available, is a separate model.</p></div></div></div>;
}

function FarmDialog({ t, onClose, onSaved }: { t: typeof copy.en; onClose: () => void; onSaved: (farm: Farm) => void }) {
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setSaving(true);
    const data = new FormData(event.currentTarget);
    const latitude = data.get("latitude")?.toString();
    const longitude = data.get("longitude")?.toString();
    try {
      const farm = await api<Farm>("/farms", { method: "POST", body: JSON.stringify({ name: data.get("name"), latitude: latitude ? Number(latitude) : null, longitude: longitude ? Number(longitude) : null, crop_variety: data.get("crop_variety") || null }) });
      onSaved(farm);
    } catch (e) { setError(e instanceof Error ? e.message : "Farm could not be saved."); }
    finally { setSaving(false); }
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="farm-dialog-title"><div className="modal-heading"><div><span className="eyebrow">FARM DETAILS</span><h2 id="farm-dialog-title">{t.addFarm}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X /></button></div><form onSubmit={(e) => void submit(e)}><label className="field-label" htmlFor="farm-name">{t.farmName}</label><input id="farm-name" name="name" className="text-input" required maxLength={120} /><p className="field-label">{t.location}</p><div className="two-fields"><label><span className="sr-only">{t.latitude}</span><input name="latitude" type="number" step="any" min="-90" max="90" className="text-input" placeholder={t.latitude} /></label><label><span className="sr-only">{t.longitude}</span><input name="longitude" type="number" step="any" min="-180" max="180" className="text-input" placeholder={t.longitude} /></label></div><label className="field-label" htmlFor="farm-crop">{t.crop}</label><input id="farm-crop" name="crop_variety" className="text-input" maxLength={120} />{error && <p className="form-error" role="alert">{error}</p>}<div className="modal-actions"><button type="button" className="secondary-button" onClick={onClose}>{t.cancel}</button><button className="primary-button" disabled={saving}>{saving ? "Saving…" : t.saveFarm}</button></div></form></section></div>;
}

function HistoryView({ t }: { t: typeof copy.en }) {
  const [diagnoses, setDiagnoses] = useState<DiagnosisHistory[]>([]);
  const [risks, setRisks] = useState<RiskHistory[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([
      api<DiagnosisHistory[]>("/diagnosis/history"),
      api<RiskHistory[]>("/risk/history"),
    ]).then(([image, risk]) => { setDiagnoses(image); setRisks(risk); })
      .catch((e) => setError(e instanceof Error ? e.message : t.failed));
  }, [t]);
  return <div className="page-enter">
    <div className="page-heading"><div><span className="eyebrow">ASSESSMENT RECORDS</span><h1>History</h1><p>Review records saved by the API.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="workspace-section"><h2>Image assessments</h2>{diagnoses.length ? <div className="record-list">{diagnoses.map((item) => <article className="record-card" key={item.id}><div><strong>{item.predicted_class ?? item.status}</strong><span>{item.status}</span></div><time>{new Date(item.created_at).toLocaleString()}</time></article>)}</div> : <div className="empty-card"><History /><div><h3>No saved image assessments</h3><p>The experimental API stores prediction metadata, never the uploaded image.</p></div></div>}</section>
    <section className="workspace-section"><h2>Risk assessments</h2>{risks.length ? <div className="record-list">{risks.map((item) => <article className="record-card" key={item.id}><div><strong>{item.disease_class}</strong><span>{item.status}</span></div><time>{new Date(item.created_at).toLocaleString()}</time></article>)}</div> : <div className="empty-card"><CloudSun /><div><h3>No saved risk assessments</h3><p>No validated environmental model is configured.</p></div></div>}</section>
  </div>;
}

function KnowledgeView({ language }: { language: Language }) {
  const [entries, setEntries] = useState<Knowledge[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    api<Knowledge[]>(`/knowledge/diseases?language=${language}`)
      .then(setEntries).catch((e) => setError(e instanceof Error ? e.message : "Knowledge could not be loaded."));
  }, [language]);
  return <div className="page-enter">
    <div className="page-heading"><div><span className="eyebrow">REVIEWED INFORMATION</span><h1>Knowledge base</h1><p>Evidence-backed guidance shown only when it is published.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    {entries.length ? <div className="knowledge-grid">{entries.map((entry) => <article className="knowledge-card" key={`${entry.disease_class}-${entry.language_code}`}><h2>{entry.display_name}</h2>{entry.scientific_name && <em>{entry.scientific_name}</em>}<h3>Symptoms</h3><p>{entry.symptoms}</p><h3>Prevention</h3><p>{entry.preventive_guidance}</p><h3>Monitoring</h3><p>{entry.monitoring_guidance}</p>{entry.management_guidance && <><h3>Management</h3><p>{entry.management_guidance}</p></>}<small>Source: {entry.source_reference}</small></article>)}</div> : <div className="empty-card"><BookOpen /><div><h3>No reviewed knowledge entries</h3><p>An administrator must publish source-backed entries.</p></div></div>}
  </div>;
}

function SettingsView({ user, language, onLanguage, onDeleted }: { user: User; language: Language; onLanguage: (language: Language) => void; onDeleted: () => Promise<void> }) {
  const [saved, setSaved] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState("");

  async function deleteAccount() {
    if (!window.confirm("Delete this account and all associated farms and history? This cannot be undone.")) return;
    setDeleting(true);
    setError("");
    try {
      await api<void>("/auth/me", { method: "DELETE" });
      await onDeleted();
    } catch (e) {
      setError(e instanceof Error ? e.message : "The account could not be deleted.");
    } finally {
      setDeleting(false);
    }
  }
  return <div className="page-enter">
    <div className="page-heading"><div><span className="eyebrow">ACCOUNT</span><h1>Settings</h1><p>Manage preferences for this workspace.</p></div></div>
    <section className="settings-panel"><h2>Profile</h2><dl><dt>Name</dt><dd>{user.full_name}</dd><dt>Email</dt><dd>{user.email}</dd><dt>Role</dt><dd>{user.role}</dd></dl><label className="field-label" htmlFor="settings-language">Interface language</label><select id="settings-language" className="text-input" value={language} onChange={(event) => { onLanguage(event.target.value as Language); setSaved(true); }}><option value="en">English</option><option value="ta">தமிழ்</option></select>{saved && <p className="form-success">Preference saved.</p>}</section>
    <section className="settings-panel danger-zone"><h2>Delete account</h2><p>Permanently remove this account, owned farms, weather cache, and prediction history.</p>{error && <p className="form-error" role="alert">{error}</p>}<button className="danger-button" type="button" onClick={() => void deleteAccount()} disabled={deleting}>{deleting ? "Deleting…" : "Delete my account"}</button></section>
  </div>;
}

function AdminView() {
  const [models, setModels] = useState<ModelVersion[]>([]);
  const [quality, setQuality] = useState<{ status: string; message: string }>({ status: "checking", message: "Checking data quality configuration…" });
  const [error, setError] = useState("");
  useEffect(() => {
    Promise.all([api<ModelVersion[]>("/admin/models"), api<{ status: string; message: string }>("/admin/data-quality")])
      .then(([items, dataQuality]) => { setModels(items); setQuality(dataQuality); })
      .catch((e) => setError(e instanceof Error ? e.message : "Administration data could not be loaded."));
  }, []);
  return <div className="page-enter">
    <div className="page-heading"><div><span className="eyebrow">ADMINISTRATION</span><h1>Model governance</h1><p>Review active artifacts and data-quality configuration.</p></div></div>
    {error && <p className="form-error" role="alert">{error}</p>}
    <section className="workspace-section"><h2>Data quality</h2><div className="model-notice"><ShieldCheck /><div><strong>{quality.status}</strong><p>{quality.message}</p></div></div></section>
    <section className="workspace-section"><h2>Registered model versions</h2>{models.length ? <div className="record-list">{models.map((item) => <article className="record-card" key={item.id}><div><strong>{item.model_type} · {item.version}</strong><span>{item.is_active ? "active" : "inactive"}</span></div><small>{item.dataset_version ?? "dataset not recorded"}</small></article>)}</div> : <div className="empty-card"><ShieldCheck /><div><h3>No model registry entries</h3><p>Artifacts are not silently registered or activated.</p></div></div>}</section>
  </div>;
}

function AuthDialog({ t, mode, setMode, onClose, onSuccess }:{ t: typeof copy.en; mode: "login" | "register"; setMode: (mode: "login" | "register") => void; onClose: () => void; onSuccess: () => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setBusy(true);
    const data = new FormData(event.currentTarget);
    const payload = { email: data.get("email"), password: data.get("password"), ...(mode === "register" ? { full_name: data.get("full_name"), preferred_language: "en" } : {}) };
    try { await api<User>(mode === "register" ? "/auth/register" : "/auth/login", { method: "POST", body: JSON.stringify(payload) }); onSuccess(); }
    catch (e) { setError(e instanceof Error ? e.message : "Sign-in failed."); }
    finally { setBusy(false); }
  }
  return <div className="modal-backdrop" role="presentation" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="auth-dialog-title"><div className="modal-heading"><div><span className="eyebrow">YOUR FIELD WORKSPACE</span><h2 id="auth-dialog-title">{mode === "login" ? t.signIn : t.signUp}</h2></div><button className="icon-button" onClick={onClose} aria-label="Close"><X /></button></div><p className="field-hint">{t.session}</p><form onSubmit={(e) => void submit(e)}>{mode === "register" && <><label className="field-label" htmlFor="auth-name">{t.name}</label><input className="text-input" id="auth-name" name="full_name" required maxLength={160} /> </>}<label className="field-label" htmlFor="auth-email">{t.email}</label><input className="text-input" id="auth-email" name="email" type="email" required autoComplete="email" /><label className="field-label" htmlFor="auth-password">{t.password}</label><input className="text-input" id="auth-password" name="password" type="password" required minLength={mode === "register" ? 12 : 1} autoComplete={mode === "register" ? "new-password" : "current-password"} />{error && <p className="form-error" role="alert">{error}</p>}<button className="primary-button submit-button" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? t.login : t.register}<ArrowRight size={17} /></button></form><button className="text-button" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}>{mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}</button></section></div>;
}
