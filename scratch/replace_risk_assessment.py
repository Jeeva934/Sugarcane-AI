path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = None
end_idx = None

for i, line in enumerate(lines):
    if line.startswith("function RiskAssessment"):
        start_idx = i
    if start_idx is not None and line.startswith("function ExplanationView"):
        end_idx = i
        break

if start_idx is None or end_idx is None:
    print(f"Error: indices not found ({start_idx}, {end_idx})")
    exit(1)

new_func = '''function RiskAssessment({ farms, t, language }: { farms: Farm[]; t: typeof copy.en; language: Language }) {
  const [farmId, setFarmId] = useState("");
  const [targetDisease, setTargetDisease] = useState("RedRot");
  const [grassAge, setGrassAge] = useState("90 days (3 Months - Tillering)");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [riskResult, setRiskResult] = useState<RiskResult | null>(null);
  const [riskModelStatus, setRiskModelStatus] = useState<"checking" | "experimental_enabled" | "disabled" | "unavailable">("checking");
  const [weather, setWeather] = useState<WeatherObservation | null>(null);
  const [weatherLoading, setWeatherLoading] = useState(false);
  const [guidanceCheckMessage, setGuidanceCheckMessage] = useState("");
  const [aiGuidance, setAiGuidance] = useState<WeatherGuidance | null>(null);
  const [aiGuidanceLanguage, setAiGuidanceLanguage] = useState<Language | null>(null);
  const [aiGuidanceRequestLanguage, setAiGuidanceRequestLanguage] = useState<Language | null>(null);
  const [aiGuidanceLoading, setAiGuidanceLoading] = useState(false);
  const [aiGuidanceError, setAiGuidanceError] = useState("");
  const aiGuidanceRequestId = useRef(0);

  const selectedFarm = farms.find((f) => f.id === farmId);

  useEffect(() => {
    let active = true;
    setWeather(null);
    setAiGuidance(null);
    setAiGuidanceError("");
    if (!selectedFarm || selectedFarm.latitude === null || selectedFarm.longitude === null) {
      setWeatherLoading(false);
      return () => { active = false; };
    }

    setWeatherLoading(true);
    api<WeatherObservation>(`/weather/current?farm_id=${selectedFarm.id}`)
      .then((result) => { if (active) setWeather(result); })
      .catch(() => { if (active) setWeather({ status: "unavailable", provider: "Open-Meteo", cached: false, timestamp: null, message: "Weather could not be retrieved. Check internet access and try again." }); })
      .finally(() => { if (active) setWeatherLoading(false); });
    return () => { active = false; };
  }, [selectedFarm?.id, selectedFarm?.latitude, selectedFarm?.longitude]);

  useEffect(() => {
    let active = true;
    api<{ checks?: { risk_model?: string; risk_models?: Record<string, string> } }>("/health/ready")
      .then((health) => {
        const status = health.checks?.risk_models?.[targetDisease] ?? health.checks?.risk_model;
        if (active) {
          setRiskModelStatus(status === "experimental_enabled" || status === "disabled" ? status : "unavailable");
        }
      })
      .catch(() => {
        if (active) setRiskModelStatus("unavailable");
      });
    return () => { active = false; };
  }, [targetDisease]);

  async function submit() {
    if (!farmId || !selectedFarm || selectedFarm.latitude === null || selectedFarm.longitude === null) {
      setError("Select a farm with saved GPS coordinates before assessing environmental risk.");
      return;
    }
    setError("");
    setAiGuidance(null);
    setAiGuidanceError("");
    setLoading(true);
    if (riskModelStatus !== "experimental_enabled") {
      setRiskResult(null);
      setGuidanceCheckMessage("");
      try {
        const refreshed = await api<WeatherObservation>(`/weather/refresh?farm_id=${selectedFarm.id}`, {
          method: "POST",
        });
        setWeather(refreshed);
        setGuidanceCheckMessage(refreshed.observation
          ? `${localizedText(language, refreshed.cached ? "Latest saved weather loaded" : "Weather refreshed")} for ${selectedFarm.name}. ${localizedText(language, "Use the Analyze weather with Gemini button to get tips from these readings.")}`
          : translate(language, refreshed.message ?? "Weather is unavailable, so no disease prediction or weather-based guidance check was generated."));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not refresh farm weather.");
      } finally {
        setLoading(false);
      }
      return;
    }
    setRiskResult(null);
    setGuidanceCheckMessage("");

    try {
      const res = await api<RiskResult>("/risk/predict", {
        method: "POST",
        body: JSON.stringify({ farm_id: farmId, disease_class: targetDisease, grass_age: grassAge })
      });
      setRiskResult(res);
    } catch (e) {
      setError(e instanceof Error ? e.message : t.riskUnavailable);
    } finally {
      setLoading(false);
    }
  }

  function clearAiGuidance() {
    aiGuidanceRequestId.current += 1;
    setAiGuidance(null);
    setAiGuidanceLanguage(null);
    setAiGuidanceRequestLanguage(null);
    setAiGuidanceLoading(false);
    setAiGuidanceError("");
  }

  async function analyzeWeather() {
    if (!selectedFarm) return;
    const requestId = ++aiGuidanceRequestId.current;
    const requestLanguage = language;
    setAiGuidance(null);
    setAiGuidanceLanguage(null);
    setAiGuidanceRequestLanguage(requestLanguage);
    setAiGuidanceError("");
    setAiGuidanceLoading(true);
    try {
      const result = await api<WeatherGuidance>("/weather/guidance", {
        method: "POST",
        body: JSON.stringify({ farm_id: selectedFarm.id, disease_class: targetDisease, language_code: requestLanguage, grass_age: grassAge }),
      });
      if (requestId === aiGuidanceRequestId.current) {
        setAiGuidance(result);
        setAiGuidanceLanguage(requestLanguage);
      }
    } catch (e) {
      if (requestId === aiGuidanceRequestId.current) {
        setAiGuidanceError(e instanceof Error ? e.message : "AI weather guidance could not be generated.");
      }
    } finally {
      if (requestId === aiGuidanceRequestId.current) {
        setAiGuidanceLoading(false);
      }
    }
  }

  useEffect(() => {
    if (
      (aiGuidance && aiGuidanceLanguage !== language)
      || (aiGuidanceLoading && aiGuidanceRequestLanguage !== language)
    ) {
      void analyzeWeather();
    }
  }, [aiGuidance, aiGuidanceLanguage, aiGuidanceLoading, aiGuidanceRequestLanguage, language]);

  return (
    <div className="page-enter">
      <div className="page-heading">
        <div>
          <span className="eyebrow"><LocalText source="AGROMETEOROLOGICAL RISK MODULE" /></span>
          <h1>{t.riskNav}</h1>
          <p><LocalText source="Farm GPS, current weather and optional soil pH. These measurements alone cannot confirm or predict a disease without locally validated disease-observation data." /></p>
        </div>
      </div>

      <div className="risk-split-layout">
        {/* LEFT COLUMN: Sticky options & farm conditions */}
        <div className="risk-left-sticky">
          {riskModelStatus !== "experimental_enabled" && (
            <p className="form-error" role="status" style={{ marginBottom: "16px" }}>
              <LocalText source={riskModelStatus === "checking"
                ? "Checking per-disease environmental model availability…"
                : riskModelStatus === "disabled"
                  ? "No verified real-world training data is available, so disease-risk predictions are turned off. Synthetic demo data is not used for predictions. Weather readings below are for monitoring only."
                  : "No trained per-disease environmental model artifact is available. Synthetic demo data is not used for predictions. Weather readings below are for monitoring only; no disease score has been generated."} />
            </p>
          )}

          <label className="field-label" htmlFor="risk-farm" style={{ marginTop: 0 }}>{t.selectFarm}</label>
          <select
            id="risk-farm"
            className="text-input"
            value={farmId}
            onChange={(e) => { setFarmId(e.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
            required
          >
            <option value=""><LocalText source="Choose a farm location" /></option>
            {farms.map((farm) => (
              <option key={farm.id} value={farm.id}>
                {farm.name} {farm.latitude !== null ? `(${farm.latitude.toFixed(2)}°N, ${farm.longitude?.toFixed(2)}°E)` : "(No coordinates)"}
              </option>
            ))}
          </select>

          <label className="field-label" htmlFor="risk-disease"><LocalText source="Disease guidance" /></label>
          <select
            id="risk-disease"
            className="text-input"
            value={targetDisease}
            onChange={(event) => { setTargetDisease(event.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
          >
            <option value="Mosaic"><LocalText source="Mosaic" /></option>
            <option value="RedRot"><LocalText source="Red rot" /></option>
            <option value="Rust"><LocalText source="Rust" /></option>
            <option value="Yellow"><LocalText source="Yellow leaf" /></option>
            <option value="Wilt"><LocalText source="Wilt" /></option>
          </select>

          <label className="field-label" htmlFor="risk-grass-age">
            <LocalText source="Grass age (Crop stage)" />
          </label>
          <select
            id="risk-grass-age"
            className="text-input"
            value={grassAge}
            onChange={(event) => { setGrassAge(event.target.value); setRiskResult(null); clearAiGuidance(); setError(""); }}
          >
            <option value="30 days (1 Month - Germination / Sprouting)">
              {localizedText(language, "30 days (1 Month - Germination / Sprouting)", "30 நாட்கள் (1 மாதம் - முளைப்பு நிலை)")}
            </option>
            <option value="60 days (2 Months - Early Tillering)">
              {localizedText(language, "60 days (2 Months - Early Tillering)", "60 நாட்கள் (2 மாதம் - ஆரம்ப தூர்க்கட்டும் நிலை)")}
            </option>
            <option value="90 days (3 Months - Tillering)">
              {localizedText(language, "90 days (3 Months - Tillering)", "90 நாட்கள் (3 மாதம் - தூர்க்கட்டும் நிலை)")}
            </option>
            <option value="120 days (4 Months - Late Tillering)">
              {localizedText(language, "120 days (4 Months - Late Tillering)", "120 நாட்கள் (4 மாதம் - தீவிர தூர்க்கட்டு)")}
            </option>
            <option value="180 days (6 Months - Grand Growth)">
              {localizedText(language, "180 days (6 Months - Grand Growth)", "180 நாட்கள் (6 மாதம் - தீவிர வளர்ச்சி நிலை)")}
            </option>
            <option value="240 days (8 Months - Stalk Elongation)">
              {localizedText(language, "240 days (8 Months - Stalk Elongation)", "240 நாட்கள் (8 மாதம் - தண்டு வளர்ச்சி நிலை)")}
            </option>
            <option value="300 days (10 Months - Early Maturity)">
              {localizedText(language, "300 days (10 Months - Early Maturity)", "300 நாட்கள் (10 மாதம் - ஆரம்ப முதிர்ச்சி நிலை)")}
            </option>
            <option value="360 days (12 Months - Harvest Maturity)">
              {localizedText(language, "360 days (12 Months - Harvest Maturity)", "360 நாட்கள் (12 மாதம் - அறுவடை நிலை)")}
            </option>
            <option value="Ratoon Crop (1st-2nd Ratoon)">
              {localizedText(language, "Ratoon Crop (1st-2nd Ratoon)", "மறுதாம்பு பயிர் (Ratoon)")}
            </option>
          </select>

          {selectedFarm && selectedFarm.latitude === null && (
            <p className="form-error" role="alert" style={{ marginTop: "12px" }}>
              <LocalText source="Coordinates are required for weather-based assessment. Edit farm to add latitude & longitude." />
            </p>
          )}

          {selectedFarm && (
            <section className="settings-panel" style={{ marginTop: "16px", padding: "16px" }} aria-live="polite">
              <h2 style={{ fontSize: "15px", marginBottom: "8px" }}><LocalText source="Farm conditions" /></h2>
              <p style={{ margin: "4px 0", fontSize: "13px" }}>
                <LocalText source="Soil pH:" /> {selectedFarm.soil_ph === null ? "Not recorded — add a soil-test result in farm details." : selectedFarm.soil_ph.toFixed(1)}
              </p>
              {weatherLoading && <p style={{ fontSize: "12px", color: "var(--muted)" }}><LocalText source="Fetching current weather for the saved farm GPS point…" /></p>}
              {!weatherLoading && weather?.observation && (
                <div style={{ marginTop: "10px", fontSize: "12px", lineHeight: "1.6" }}>
                  <p style={{ color: "#475569", fontWeight: "600", margin: "2px 0" }}>
                    {localizedText(language, weather.cached ? "Cached" : "Current")} <LocalText source="weather from" /> {weather.provider}
                    {weather.timestamp ? ` · ${new Date(weather.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "6px", marginTop: "8px" }}>
                    <div style={{ background: "#f8fafc", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                      <span style={{ color: "#64748b", fontSize: "11px", display: "block" }}><LocalText source="Temperature" /></span>
                      <strong>{weather.observation.temperature_mean === null ? "—" : `${weather.observation.temperature_mean.toFixed(1)} °C`}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                      <span style={{ color: "#64748b", fontSize: "11px", display: "block" }}><LocalText source="Humidity" /></span>
                      <strong>{weather.observation.relative_humidity === null ? "—" : `${weather.observation.relative_humidity.toFixed(0)}%`}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                      <span style={{ color: "#64748b", fontSize: "11px", display: "block" }}><LocalText source="Rain" /></span>
                      <strong>{weather.observation.precipitation === null ? "—" : `${weather.observation.precipitation.toFixed(1)} mm`}</strong>
                    </div>
                    <div style={{ background: "#f8fafc", padding: "6px 8px", borderRadius: "6px", border: "1px solid #e2e8f0" }}>
                      <span style={{ color: "#64748b", fontSize: "11px", display: "block" }}><LocalText source="Wind" /></span>
                      <strong>{weather.observation.wind_speed === null ? "—" : `${weather.observation.wind_speed.toFixed(1)} km/h`}</strong>
                    </div>
                  </div>
                </div>
              )}
              {!weatherLoading && !weather?.observation && selectedFarm.latitude !== null && (
                <p className="form-error" role="status"><LocalText source={weather?.message ?? "No weather observations are available for this farm yet."} /></p>
              )}
            </section>
          )}

          {error && <p className="form-error" role="alert" style={{ marginTop: "14px" }}><LocalText source={error} /></p>}
          {guidanceCheckMessage && <p className="form-success" role="status" style={{ marginTop: "14px" }}><LocalText source={guidanceCheckMessage} /></p>}

          <button
            type="button"
            className="primary-button submit-button"
            style={{ width: "100%", marginTop: "16px" }}
            disabled={!farmId || loading || !selectedFarm || selectedFarm.latitude === null || selectedFarm.longitude === null}
            onClick={() => void submit()}
          >
            {loading
              ? riskModelStatus === "experimental_enabled" ? t.checkingRisk : localizedText(language, "Refreshing weather…")
              : riskModelStatus === "experimental_enabled" ? t.runRisk : localizedText(language, "Refresh weather")}
            <ArrowRight size={17} />
          </button>
        </div>

        {/* RIGHT COLUMN: Scrollable Content & Gemini Research */}
        <div className="risk-right-scrollable">
          {/* Card 1: Gemini AI Weather Research */}
          <div className="gemini-research-card">
            <div className="gemini-action-bar">
              <div>
                <span className="eyebrow" style={{ color: "#2563eb" }}>
                  {localizedText(language, "AGROMETEOROLOGICAL AI ANALYSIS", "வானிலை நோய் தொற்று ஆராய்ச்சி")}
                </span>
                <h2 style={{ fontSize: "19px", margin: "4px 0 0", color: "#1e293b", display: "flex", alignItems: "center", gap: "8px" }}>
                  <Sparkles size={19} color="#2563eb" />
                  {localizedText(language, "AI Weather Research", " AI வானிலை ஆராய்ச்சி")}
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void analyzeWeather()}
                disabled={aiGuidanceLoading || weatherLoading || !selectedFarm || selectedFarm.latitude === null || !weather?.observation}
              >
                <Sparkles size={16} />
                {aiGuidanceLoading
                  ? localizedText(language, "Analyzing weather…", "வானிலை ஆராய்கிறது…")
                  : localizedText(language, "Analyze weather with Gemini", "Gemini மூலம் வானிலை ஆராய்க")}
              </button>
            </div>

            {aiGuidanceError && <p className="form-error" role="alert" style={{ marginTop: "14px" }}><LocalText source={aiGuidanceError} /></p>}

            {/* Direct Gemini research results shown right below the button */}
            {aiGuidance && (
              <div className="ai-weather-guidance" style={{ marginTop: "18px", border: "none", padding: 0 }} aria-live="polite">
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: "10px", background: "#f8fafc", padding: "12px 16px", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
                  <div>
                    <span style={{ fontSize: "12px", color: "#64748b", textTransform: "uppercase", fontWeight: "700", display: "block" }}>
                      {localizedText(language, "Predicted Risk Level", "கணிக்கப்பட்ட அபாய நிலை")}
                    </span>
                    <strong style={{ fontSize: "18px" }}>{weatherRiskLabel(aiGuidance.risk_level, language)}</strong>
                  </div>
                  <div style={{ textAlign: "right" }}>
                    <small style={{ color: "#64748b", display: "block" }}>
                      {localizedText(language, "Grass Age: ", "பயிர் வயது: ")}<strong>{grassAge}</strong>
                    </small>
                    <small style={{ color: "#64748b" }}>
                      Gemini {aiGuidance.model} · {new Date(aiGuidance.weather_observed_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </small>
                  </div>
                  <SpeechButton
                    text={[
                      aiGuidance.summary,
                      aiGuidance.risk_reason,
                      aiGuidance.weather_effect,
                      `${localizedText(language, "What to do", "என்ன செய்வது")}: ${aiGuidance.actions.join(". ")}`,
                      aiGuidance.watch_for.length
                        ? `${localizedText(language, "What to watch for", "என்ன பார்க்க வேண்டும்")}: ${aiGuidance.watch_for.join(". ")}`
                        : "",
                      aiGuidance.limitations,
                    ].filter(Boolean).join(". ")}
                    lang={language}
                    label={localizedText(language, "Listen to AI explanation", "விளக்கத்தைக் கேளுங்கள்")}
                  />
                </div>

                <div style={{ marginTop: "16px" }}>
                  <h3 style={{ fontSize: "17px", color: "#1e293b", margin: "0 0 8px" }}>{aiGuidance.summary}</h3>
                  <p style={{ fontSize: "14px", lineHeight: "1.6", color: "#334155", margin: "0 0 12px" }}>{aiGuidance.risk_reason}</p>
                  <p style={{ fontSize: "13px", lineHeight: "1.6", color: "#64748b", background: "#f1f5f9", padding: "10px 14px", borderRadius: "6px" }}>
                    <strong>{localizedText(language, "Meteorological Impact:", "வானிலை தாக்கம்:")}</strong> {aiGuidance.weather_effect}
                  </p>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "16px" }}>
                  <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0", padding: "14px", borderRadius: "8px" }}>
                    <strong style={{ color: "#166534", fontSize: "13px", display: "block", marginBottom: "6px" }}>
                      ✓ {localizedText(language, "What to do (Field Actions)", "என்ன செய்ய வேண்டும் (கள நடவடிக்கைகள்)")}
                    </strong>
                    <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "#14532d", lineHeight: "1.6" }}>
                      {aiGuidance.actions.map((action, index) => <li key={`action-${index}`}>{action}</li>)}
                    </ul>
                  </div>

                  <div style={{ background: "#fefce8", border: "1px solid #fef08a", padding: "14px", borderRadius: "8px" }}>
                    <strong style={{ color: "#854d0e", fontSize: "13px", display: "block", marginBottom: "6px" }}>
                      🔍 {localizedText(language, "What to watch for (Scouting Signs)", "கண்காணிக்க வேண்டிய அறிகுறிகள்")}
                    </strong>
                    <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "13px", color: "#713f12", lineHeight: "1.6" }}>
                      {aiGuidance.watch_for.map((item, index) => <li key={`watch-${index}`}>{item}</li>)}
                    </ul>
                  </div>
                </div>

                <p className="field-hint" style={{ marginTop: "14px" }}>{aiGuidance.limitations}</p>
              </div>
            )}

            {!aiGuidance && !aiGuidanceLoading && (
              <p style={{ color: "#64748b", fontSize: "13px", marginTop: "14px", background: "#f8fafc", padding: "14px", borderRadius: "8px" }}>
                {localizedText(
                  language,
                  "Click 'Analyze weather with Gemini' above to generate an in-depth epidemiological screening based on your farm's 7-day microclimatic trends and selected grass age.",
                  "உங்கள் பண்ணையின் 7 நாள் வானிலை போக்குகள் மற்றும் பயிர் வயதின் அடிப்படையில் விரிவான நோய் அபாய ஆய்வைப் பெற மேலே உள்ள 'Analyze weather with Gemini' பொத்தானைக் கிளிக் செய்யவும்."
                )}
              </p>
            )}
          </div>

          {/* Card 2: Risk Result Card (Option 2 Result) */}
          {riskResult && (
            <article className="risk-result-card" style={{ marginTop: 0 }}>
              <div className="risk-header-row">
                <div>
                  <span className="eyebrow">{t.leadTimeBadge}</span>
                  <h2 style={{ fontSize: "22px", margin: "4px 0", color: "#1e293b" }}>
                    {diseaseLabel(riskResult.disease_class, language)}: {(riskResult.disease_presence_score * 100).toFixed(0)}% {localizedText(language, "model score (not a diagnosis)", "மாதிரி மதிப்பெண் (நோய் உறுதி அல்ல)")}
                  </h2>
                </div>
              </div>

              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "14px" }}>
                <span style={{ fontSize: "13px", color: "#64748b" }}>
                  <LocalText source={riskResult.score_note} />
                </span>
                <SpeechButton
                  text={
                    `${localizedText(language, "A model score for", "நோய்க்கான மாதிரி மதிப்பெண்")} ${diseaseLabel(riskResult.disease_class, language)}. ${localizedText(language, "It does not confirm disease or predict the future.", "இது நோய் உறுதியும் எதிர்கால கணிப்பும் அல்ல.")}`
                  }
                  lang={language}
                />
              </div>

              {riskResult.age_ai_guidance && (
                <div className="model-notice" style={{ marginBottom: "14px", background: "#f0fdf4", borderColor: "#86efac", color: "#14532d" }}>
                  <ShieldCheck />
                  <div>
                    <strong>{localizedText(language, "Grass Age & Physiological Advisory (Gemini AI)", "பயிர் வயது மற்றும் உடலியல் வழிகாட்டல் (Gemini AI)")}</strong>
                    <p style={{ margin: "4px 0", fontSize: "13px", lineHeight: "1.5" }}>{riskResult.age_ai_guidance}</p>
                    <small style={{ color: "#166534", fontWeight: "600" }}>
                      {localizedText(language, "Evaluated Cane Age: ", "மதிப்பிடப்பட்ட பயிர் வயது: ")}{riskResult.grass_age}
                    </small>
                  </div>
                </div>
              )}

              <div className="shap-list">
                <strong style={{ fontSize: "12px", color: "#475569", textTransform: "uppercase" }}>{t.primaryDrivers}</strong>
                {riskResult.primary_drivers.map((d, i) => (
                  <div key={i} className="shap-item">
                    <span>{riskFeatureLabel(d.feature, language)}: <strong>{d.value ?? localizedText(language, "not recorded", "பதிவில்லை")}</strong></span>
                    <span className={d.shap_value > 0 ? "shap-inc" : "shap-dec"}>
                      {d.shap_value > 0
                        ? localizedText(language, "raised the model score", "மதிப்பை உயர்த்தியது")
                        : localizedText(language, "lowered the model score", "மதிப்பைக் குறைத்தது")}
                    </span>
                  </div>
                ))}
              </div>

              <p className="result-warning" style={{ marginTop: "14px" }}>
                {localizedText(language, "This is an experimental model result, not a diagnosis. Weather-based disease prediction is currently disabled.", "இந்த முடிவு சோதனை மாதிரியிலிருந்து வருகிறது; நோய் உறுதிப்படுத்தாது. வானிலை நோய் கணிப்பு தற்போது முடக்கப்பட்டுள்ளது.")}
              </p>
            </article>
          )}

          <div className="explain-banner compact" style={{ maxWidth: "100%", marginTop: 0 }}>
            <CircleHelp />
            <div>
              <h3>{localizedText(language, "Weather and leaf photo", "வானிலை மற்றும் இலைப் படம்")}</h3>
              <p>{localizedText(language, "The photo checks for visible signs. Weather alone cannot confirm disease.", "இலைப் படம் அறிகுறியைத் தேடும். வானிலை மட்டும் நோயை உறுதி செய்யாது.")}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
'''

new_lines = lines[:start_idx] + [new_func + "\n"] + lines[end_idx:]

with open(path, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Replaced RiskAssessment successfully.")

