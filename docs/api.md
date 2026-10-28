# API reference

The interactive OpenAPI UI is available at `/docs` when the backend is running.
All application endpoints use `/api/v1`.

| Area | Routes |
|---|---|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /auth/me`; `PATCH /auth/me` |
| Farms | `GET/POST /farms`; `GET/PATCH/DELETE /farms/{farm_id}` |
| Weather | `GET /weather/current?farm_id=...`, `GET /weather/history?farm_id=...`, `POST /weather/refresh?farm_id=...` |
| Risk | `POST /risk/predict`, `GET /risk/history`, `GET /risk/{prediction_id}`, `GET /risk/{prediction_id}/explanation` |
| Image diagnosis | `POST /diagnosis/predict` (multipart `file`, optional `farm_id` query); `GET /diagnosis/history`, `GET /diagnosis/{diagnosis_id}`, `GET /diagnosis/{diagnosis_id}/heatmap` |
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
It does not save the image or result to history or provide a heatmap. These
outputs are not independently field-validated diagnoses; see
[ML workflow](../ml/README.md).
