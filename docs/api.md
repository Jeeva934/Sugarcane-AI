# API reference

The interactive OpenAPI UI is available at `/docs` when the backend is running.
All application endpoints use `/api/v1`.

| Area | Routes |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /auth/me`; `PATCH /auth/me` |
| Farms | `GET/POST /farms`; `GET/PATCH/DELETE /farms/{farm_id}` |
| Weather | `GET /weather/current?farm_id=...`, `GET /weather/history?farm_id=...`, `POST /weather/refresh?farm_id=...`, `POST /weather/guidance` |
| Risk | `POST /risk/predict`, `GET /risk/history`, `GET /risk/{prediction_id}`, `GET /risk/{prediction_id}/explanation` |
| Image diagnosis | `POST /diagnosis/predict` (multipart `file`, optional `farm_id` query); `GET /diagnosis/history`, `GET /diagnosis/{diagnosis_id}`, `GET /diagnosis/{diagnosis_id}/heatmap` |
| Synthetic demonstration | `POST /demo/fusion/predict` (development only; multipart `file` and `farm_id`) |
| Knowledge | `GET /knowledge/diseases?language=en|ta`, `GET /knowledge/diseases/{disease_class}?language=en|ta` |
| Admin | `GET /admin/models`, `POST /admin/knowledge`, `PATCH /admin/knowledge/{knowledge_id}`, `GET /admin/data-quality` |
| Health | `GET /health/live`, `GET /health/ready` |

Authentication uses an HttpOnly, SameSite session cookie. Configure secure
cookies and HTTPS in production. `/auth/forgot-password` is omitted until an
email delivery provider and token lifecycle are configured. Image diagnosis
returns `503` with a structured unavailability code by default. Experimental
inference requires both `IMAGE_MODEL_PATH` and
`ENABLE_EXPERIMENTAL_IMAGE_MODEL=true`, plus the optional dependencies in
`ml/requirements.txt`. When enabled, `POST /diagnosis/predict` returns an
experimental class, uncalibrated softmax scores, model version, and a warning.
It saves prediction metadata but not the uploaded image, and includes a
Grad-CAM++ heatmap when it can be generated. These outputs are not independently
field-validated diagnoses; see
[ML workflow](../ml/README.md).

The development-only `POST /demo/fusion/predict` route combines the
experimental EfficientNetV2 output with synthetic-only XGBoost scores and
returns a demonstration-only late-fusion ranking, SHAP drivers, an ALE plot,
and Grad-CAM++ visualization. It is hidden in production and does not create
diagnosis or risk history records. Synthetic scores are not real disease
signals and must not guide farm decisions. Wilt is omitted from fusion because
the current image classifier has no Wilt class. YOLO is not run because no
bounding-box dataset or trained detector artifact is available.

`POST /weather/guidance` accepts `{ "farm_id": "...", "disease_class": "RedRot" }`
and an optional supported `language_code`. It requires an authenticated user,
a farm with GPS coordinates, an available current or cached weather observation,
and a backend `GEMINI_API_KEY`. The selected language is used when supplied;
otherwise, the user's saved interface language is used. The response includes
the current weather readings, the count of recent weather days used, and a
validated preliminary environmental risk screening with reasons and safe
monitoring actions. The backend retrieves up to seven previous days of hourly
weather estimates from Open-Meteo and summarizes it by day. These gridded
provider estimates are not on-farm sensor measurements. Exact farm GPS coordinates,
weather, selected disease, and saved crop/soil details are sent to Gemini; the
UI discloses this before the action. This is not a validated disease model,
diagnosis, or forecast. Keep the Gemini key in the backend environment; never
put it in frontend configuration.
