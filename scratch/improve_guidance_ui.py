path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add auto-selection of first farm
old_selected_farm = """  const selectedFarm = farms.find((f) => f.id === farmId);"""

new_selected_farm = """  const selectedFarm = farms.find((f) => f.id === farmId);

  useEffect(() => {
    if (!farmId && farms.length > 0) {
      setFarmId(farms[0].id);
    }
  }, [farms, farmId]);"""

content = content.replace(old_selected_farm, new_selected_farm, 1)

# 2. Improve analyzeWeather with validation checks
old_analyze_weather = """  async function analyzeWeather() {
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
  }"""

new_analyze_weather = """  async function analyzeWeather() {
    if (!selectedFarm) {
      setAiGuidanceError(localizedText(language, "Please choose a farm location from the left panel first.", "முதலில் இடது பேனலில் ஒரு பண்ணையைத் தேர்ந்தெடுக்கவும்."));
      return;
    }
    if (selectedFarm.latitude === null || selectedFarm.longitude === null) {
      setAiGuidanceError(localizedText(language, "Farm GPS coordinates are required before requesting weather guidance. Edit farm to add coordinates.", "வானிலை வழிகாட்டலுக்கு பண்ணை GPS தேவை. அட்சரேகையைச் சேர்க்க பண்ணையைத் திருத்தவும்."));
      return;
    }
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
  }"""

content = content.replace(old_analyze_weather, new_analyze_weather, 1)

# 3. Update the button disabled state and add visual loading feedback
old_button_block = """              <button
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

            {aiGuidanceError && <p className="form-error" role="alert" style={{ marginTop: "14px" }}><LocalText source={aiGuidanceError} /></p>}"""

new_button_block = """              <button
                type="button"
                onClick={() => void analyzeWeather()}
                disabled={aiGuidanceLoading || weatherLoading}
              >
                <Sparkles size={16} />
                {aiGuidanceLoading
                  ? localizedText(language, "Analyzing weather…", "வானிலை ஆராய்கிறது…")
                  : localizedText(language, "Analyze weather with Gemini", "Gemini மூலம் வானிலை ஆராய்க")}
              </button>
            </div>

            {aiGuidanceError && <p className="form-error" role="alert" style={{ marginTop: "14px" }}><LocalText source={aiGuidanceError} /></p>}

            {/* Glowing animated loading state */}
            {aiGuidanceLoading && (
              <div style={{ padding: "28px", textAlign: "center", background: "#f8fafc", borderRadius: "10px", border: "1px dashed #93c5fd", marginTop: "18px" }}>
                <div style={{ display: "inline-block", width: "28px", height: "28px", border: "3px solid #bfdbfe", borderTopColor: "#2563eb", borderRadius: "50%", animation: "spin 1s linear infinite", marginBottom: "10px" }} />
                <strong style={{ display: "block", color: "#1e293b", fontSize: "15px" }}>
                  {localizedText(language, "Gemini AI is analyzing 7-day microclimate & grass age...", "Gemini AI 7 நாள் வானிலை மற்றும் பயிர் வயதை ஆராய்கிறது...")}
                </strong>
                <p style={{ margin: "6px 0 0", color: "#64748b", fontSize: "13px" }}>
                  {localizedText(language, "Screening temperature, relative humidity, rain accumulation, and pathogen vulnerability.", "வெப்பநிலை, ஈரப்பதம், மழை அளவு மற்றும் நோய்க்கிருமி தாக்கத்தை மதிப்பிடுகிறது.")}
                </p>
              </div>
            )}"""

content = content.replace(old_button_block, new_button_block, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated guidance UI feedback in App.tsx successfully.")

