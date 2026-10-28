from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from time import perf_counter

from PIL import Image, UnidentifiedImageError

from app.core.config import settings

EXPECTED_CLASSES = ("Healthy", "Mosaic", "RedRot", "Rust", "Yellow")
_load_lock = Lock()


class ImageModelUnavailable(Exception):
    pass


@lru_cache(maxsize=2)
def _load_model(model_path: str):
    path = Path(model_path)
    if not path.is_file():
        raise ImageModelUnavailable("Configured image model artifact was not found.")
    try:
        import torch
        from torch import nn
        from torchvision import models, transforms
    except ImportError as exc:
        raise ImageModelUnavailable("Install the optional ML dependencies to use the image classifier.") from exc

    try:
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        if not isinstance(checkpoint, dict) or checkpoint.get("architecture") != "torchvision.efficientnet_v2_s":
            raise ImageModelUnavailable("Image model artifact has an unsupported architecture.")
        class_names = checkpoint.get("class_names")
        input_size = checkpoint.get("input_size")
        normalization = checkpoint.get("normalization")
        state_dict = checkpoint.get("state_dict")
        if (
            class_names != list(EXPECTED_CLASSES)
            or not isinstance(input_size, int)
            or input_size < 96
            or not isinstance(normalization, dict)
            or not isinstance(state_dict, dict)
        ):
            raise ImageModelUnavailable("Image model artifact metadata is invalid.")

        model = models.efficientnet_v2_s(weights=None)
        model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(class_names))
        model.load_state_dict(state_dict, strict=True)
        model.eval()
        preprocess = transforms.Compose([
            transforms.Resize(input_size + 32),
            transforms.CenterCrop(input_size),
            transforms.ToTensor(),
            transforms.Normalize(tuple(normalization["mean"]), tuple(normalization["std"])),
        ])
    except ImageModelUnavailable:
        raise
    except (OSError, RuntimeError, EOFError, KeyError, TypeError, ValueError) as exc:
        raise ImageModelUnavailable("Image model artifact could not be loaded.") from exc
    return torch, model, preprocess, tuple(class_names), checkpoint.get("model_version", path.stem)


def classify_image(image_bytes: bytes) -> dict:
    if not settings.enable_experimental_image_model:
        raise ImageModelUnavailable("Experimental image inference is disabled.")
    if not settings.image_model_path:
        raise ImageModelUnavailable("No image model artifact is configured.")

    with _load_lock:
        torch, model, preprocess, class_names, model_version = _load_model(settings.image_model_path)
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Uploaded content is not a supported image.") from exc

    started = perf_counter()
    tensor = preprocess(image).unsqueeze(0)
    with torch.inference_mode():
        scores = torch.softmax(model(tensor), dim=1)[0].tolist()
    ranked = sorted(
        ({"disease_class": name, "uncalibrated_score": float(score)} for name, score in zip(class_names, scores)),
        key=lambda item: item["uncalibrated_score"],
        reverse=True,
    )
    return {
        "status": "experimental",
        "predicted_class": ranked[0]["disease_class"],
        "uncalibrated_score": ranked[0]["uncalibrated_score"],
        "alternative_predictions": ranked[1:3],
        "model_version": model_version,
        "processing_time_ms": round((perf_counter() - started) * 1000),
        "explanation": None,
        "warning": "Experimental model output from a single public dataset. Scores are uncalibrated; this is not a confirmed diagnosis or field-validated advice.",
        "saved_to_history": False,
    }
