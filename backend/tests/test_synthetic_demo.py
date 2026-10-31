import io
import json
from datetime import datetime, timezone
from types import SimpleNamespace

from PIL import Image
import pytest


def _image_bytes():
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), color=(30, 120, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def test_synthetic_fusion_demo_is_separate_and_not_persisted(client, monkeypatch, tmp_path):
    import app.api.routes as routes
    from backend.tests.test_api import register

    register(client, "synthetic-demo@example.com")
    farm = client.post(
        "/api/v1/farms",
        json={"name": "Demo field", "latitude": 10.5, "longitude": 78.2, "soil_ph": 6.4},
    ).json()

    model_path = tmp_path / "efficientnet_v2_s.pt"
    model_path.write_bytes(b"test artifact")
    monkeypatch.setattr(routes.settings, "enable_experimental_image_model", True)
    monkeypatch.setattr(routes.settings, "image_model_path", str(model_path))
    monkeypatch.setattr(
        routes,
        "fetch_current_weather",
        lambda farm, db: SimpleNamespace(
            source="Open-Meteo",
            observed_at=datetime.now(timezone.utc),
            temperature_mean=29.5,
            relative_humidity=84.5,
            precipitation=5.0,
            wind_speed=6.0,
            dew_point=25.8,
        ),
    )
    monkeypatch.setattr(
        routes,
        "classify_image",
        lambda image: {
            "predicted_class": "RedRot",
            "uncalibrated_score": 0.7,
            "class_scores": {
                "Healthy": 0.05,
                "Mosaic": 0.05,
                "RedRot": 0.7,
                "Rust": 0.1,
                "Yellow": 0.1,
            },
            "heatmap_base64": "heatmap",
            "model_version": "test-image-model",
        },
    )
    monkeypatch.setattr(
        routes,
        "run_synthetic_fusion_demo",
        lambda scores, features: {
            "status": "synthetic_demo_only",
            "synthetic_demo_only": True,
            "ranked_scores": [],
            "not_fused_classes": {"Wilt": "No matching image class."},
            "explanation_disease": "RedRot",
            "shap_drivers": [],
            "ale_plot_base64": "ale",
            "warning": "Synthetic demo only.",
        },
    )

    response = client.post(
        "/api/v1/demo/fusion/predict",
        data={"farm_id": farm["id"]},
        files={"file": ("leaf.jpg", _image_bytes(), "image/jpeg")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["synthetic_demo_only"] is True
    assert result["saved_to_history"] is False
    assert result["detector"]["status"] == "not_used"
    assert result["image"]["predicted_class"] == "RedRot"
    assert client.get("/api/v1/diagnosis/history").json() == []
    assert client.get("/api/v1/risk/history").json() == []


def test_synthetic_demo_artifacts_reject_non_demo_metadata(tmp_path):
    from app.services.synthetic_demo_predictor import (
        SyntheticDemoUnavailable,
        _validate_demo_artifacts,
    )
    (tmp_path / "SYNTHETIC_DEMO_ONLY_report.json").write_text(
        json.dumps({
            "real_world_validity": True,
            "safe_for_api_prediction": True,
            "target_column": "outcome",
            "warning": "Verified data",
        }),
        encoding="utf-8",
    )

    with pytest.raises(SyntheticDemoUnavailable):
        _validate_demo_artifacts(tmp_path)


def test_synthetic_fusion_demo_returns_shap_and_ale_when_artifacts_exist():
    pytest.importorskip("xgboost")
    pytest.importorskip("shap")
    pytest.importorskip("pandas")
    from app.services.synthetic_demo_predictor import (
        DEMO_ARTIFACT_DIR,
        run_synthetic_fusion_demo,
    )

    required_artifacts = (
        DEMO_ARTIFACT_DIR / "SYNTHETIC_DEMO_ONLY_report.json",
        DEMO_ARTIFACT_DIR / "demo_xgboost_redrot.json",
        DEMO_ARTIFACT_DIR / "SYNTHETIC_DEMO_ONLY_ale_redrot.png",
    )
    if not all(path.is_file() for path in required_artifacts):
        pytest.skip("Local synthetic demo artifacts are not installed.")

    result = run_synthetic_fusion_demo(
        {
            "Healthy": 0.1,
            "Mosaic": 0.1,
            "RedRot": 0.5,
            "Rust": 0.15,
            "Yellow": 0.15,
        },
        {
            "soil_ph": 6.4,
            "temperature_c": 29.5,
            "relative_humidity_pct": 84.5,
            "rainfall_mm": 5.0,
            "wind_speed_kmh": 6.0,
            "dew_point_c": 25.8,
        },
    )

    assert result["status"] == "synthetic_demo_only"
    assert len(result["ranked_scores"]) == 4
    assert result["not_fused_classes"].keys() == {"Wilt"}
    assert result["shap_drivers"]
    assert result["ale_plot_base64"]


def test_synthetic_fusion_demo_is_hidden_in_production(client, monkeypatch):
    from app.api.routes import settings
    from backend.tests.test_api import register

    register(client, "production-demo@example.com")
    monkeypatch.setattr(settings, "app_env", "production")

    response = client.post(
        "/api/v1/demo/fusion/predict",
        data={"farm_id": "unused"},
        files={"file": ("leaf.jpg", _image_bytes(), "image/jpeg")},
    )

    assert response.status_code == 404
