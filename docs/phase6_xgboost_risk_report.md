# Environmental Risk Module — Data and Model Status

**Status:** Data collection and training workflow implemented; no trained environmental disease model is included or active.

## What the application currently does

- Stores farm coordinates and an optional user-entered soil-test pH in SQLite.
- Requests current temperature, relative humidity, precipitation, wind speed, and dew point for the saved farm GPS point from Open-Meteo. If the provider cannot be reached, the UI may show a cached observation and marks it as cached.
- Lets a signed-in farmer record a suspected disease observation. This is a report, not a diagnosis or verified training label.
- Captures available weather context with the report. Research export is opt-in and does not include account details or free-text notes.
- Restricts verification and consented training-data export to administrators. A reviewer must record the evidence method and reference before an observation becomes verified.
- Keeps disease predictions unavailable until a model artifact exists. No weather-derived or synthetic disease labels are generated.

Browser GPS requires permission and records one point, not the boundary of the farmer's land. Soil pH is not supplied by the weather provider; it must come from a soil test and be entered by the user.

## Verified-data training workflow

The admin page exports consented and expert-verified observations to:

```text
datasets/environmental/verified-environmental-observations.csv
```

Train the per-disease XGBoost presence/absence research models with:

```powershell
python -m pip install -r ml\requirements.txt
python ml\train_risk_model.py --data datasets\environmental\verified-environmental-observations.csv
```

The script requires verified labels, explicit research consent, weather features, at least ten distinct observation dates, and at least ten positive and ten negative labels for each disease in each chronological train, validation, and test partition. It does not create labels from weather thresholds. It writes XGBoost artifacts, chronological test metrics, SHAP global feature values, and ALE plots under `artifacts\environmental\`.

The current data-capture record pairs weather at the time of a field observation with a reviewed observation at that time. A model trained from those records is an observation-time association model, **not a forecast of disease in the next 7 days**. A forward forecast requires appropriately timed future outcomes, a defined lead window, enough independently collected observations, and independent field validation. The app does not automatically activate a trained artifact.

## Removed unsupported claims

Earlier drafts reported 4,344 records, disease-risk model metrics, spatial generalization, and SHAP/ALE plots as completed. The matching dataset and generated artifacts are not present in this repository, so those results cannot be reproduced or verified and are not reported here.

The sugarcane leaf-image dataset is a separate input for image classification. It is not weather-linked disease incidence data and must not be used to train this environmental model.
