import pytest

from app.services.verified_risk_predictor import (
    RiskModelUnavailable,
    has_any_model,
    has_model,
    model_artifact_path,
    predict_disease_presence,
)


def test_per_disease_artifact_paths_match_training_output(tmp_path):
    artifact = tmp_path / "xgboost_redrot.json"
    artifact.write_text("test-only artifact", encoding="utf-8")
    (tmp_path / "demo_xgboost_mosaic.json").write_text("demo-only artifact", encoding="utf-8")

    assert model_artifact_path(str(tmp_path / "xgboost_risk_prototype.json"), "RedRot") == artifact
    assert has_model(str(tmp_path), "RedRot")
    assert has_any_model(str(tmp_path))


def test_synthetic_demo_artifacts_are_not_discovered_for_api_inference(tmp_path):
    demo_dir = tmp_path / "environmental_demo"
    demo_dir.mkdir()
    (demo_dir / "demo_xgboost_redrot.json").write_text("demo-only artifact", encoding="utf-8")

    assert not has_any_model(str(demo_dir))
    assert not has_model(str(demo_dir), "RedRot")


def test_missing_disease_artifact_never_generates_a_score(tmp_path):
    with pytest.raises(RiskModelUnavailable, match="No trained environmental model"):
        predict_disease_presence(
            "RedRot",
            {
                "soil_ph": None,
                "temperature_c": 29.0,
                "relative_humidity_pct": 80.0,
                "rainfall_mm": 1.0,
                "wind_speed_kmh": 7.0,
                "dew_point_c": 24.0,
            },
            str(tmp_path),
        )


def test_unknown_disease_class_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported disease class"):
        model_artifact_path(str(tmp_path), "CompositeRisk")
