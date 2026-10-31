# Update styles.css
css_path = "frontend/src/styles.css"
with open(css_path, "r", encoding="utf-8") as f:
    css = f.read()

new_styles = """

/* Sticky 2-Column Split Layout for Weather & Disease */
.risk-split-layout {
  display: grid;
  grid-template-columns: 420px minmax(0, 1fr);
  gap: 24px;
  align-items: flex-start;
  margin-top: 20px;
}

@media (max-width: 1024px) {
  .risk-split-layout {
    grid-template-columns: 1fr;
  }
}

.risk-left-sticky {
  position: sticky;
  top: 96px;
  max-height: calc(100vh - 120px);
  overflow-y: auto;
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 22px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}

.risk-right-scrollable {
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
}

.gemini-research-card {
  background: #ffffff;
  border: 1px solid #dbeafe;
  border-radius: 12px;
  padding: 22px;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.05);
}

.gemini-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid #edf2f7;
}

.gemini-action-bar button {
  background: #2563eb;
  color: #ffffff;
  border: 1px solid #1d4ed8;
  font-weight: 700;
  padding: 10px 18px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.gemini-action-bar button:hover:not(:disabled) {
  background: #1d4ed8;
}

.gemini-action-bar button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
"""

if ".risk-split-layout" not in css:
    css += new_styles
    with open(css_path, "w", encoding="utf-8") as f:
        f.write(css)
    print("Appended styles to styles.css")
else:
    print("Styles already present in styles.css")

