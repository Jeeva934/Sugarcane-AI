path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add Sparkles to lucide-react import
content = content.replace(
    "Settings, ShieldCheck, Sprout, Upload, Volume2, Wifi, WifiOff, X",
    "Settings, ShieldCheck, Sparkles, Sprout, Upload, Volume2, Wifi, WifiOff, X"
)

# Use geminiGpsDisclosure in the card
content = content.replace(
    '<p className="field-hint" style={{ marginTop: "14px" }}>{aiGuidance.limitations}</p>',
    '<p className="field-hint" style={{ marginTop: "14px" }}>{aiGuidance.limitations} · {geminiGpsDisclosure[language]}</p>'
)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("Updated Sparkles and geminiGpsDisclosure successfully.")

