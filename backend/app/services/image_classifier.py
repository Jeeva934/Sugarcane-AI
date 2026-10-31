import base64
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock
from time import perf_counter

import cv2
import numpy as np
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


def compute_gradcam_overlay(torch, model, preprocess, orig_image: Image.Image, target_idx: int) -> str | None:
    try:
        import torch.nn.functional as F

        target_layer = model.features[-1]
        activations = []
        gradients = []

        def forward_hook(module, input, output):
            activations.append(output)

        def backward_hook(module, grad_in, grad_out):
            gradients.append(grad_out[0])

        h1 = target_layer.register_forward_hook(forward_hook)
        h2 = target_layer.register_full_backward_hook(backward_hook)

        tensor = preprocess(orig_image).unsqueeze(0)
        tensor.requires_grad_(True)

        logits = model(tensor)
        score = logits[0, target_idx]

        model.zero_grad()
        score.backward()

        h1.remove()
        h2.remove()

        if not activations or not gradients:
            return None

        acts = activations[0]
        grads = gradients[0]

        grads_2 = grads.pow(2)
        grads_3 = grads.pow(3)
        sum_acts = acts.sum(dim=(2, 3), keepdim=True)
        eps = 1e-7
        aij = grads_2 / (2 * grads_2 + sum_acts * grads_3 + eps)
        aij = torch.where(grads != 0, aij, torch.zeros_like(aij))

        weights = (aij * F.relu(grads)).sum(dim=(2, 3), keepdim=True)
        cam = (weights * acts).sum(dim=1, keepdim=True)
        cam = F.relu(cam)

        cam_min, cam_max = cam.min(), cam.max()
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = torch.zeros_like(cam)

        cam_np = cam.squeeze().detach().cpu().numpy()

        w, h = orig_image.size
        cam_resized = cv2.resize(cam_np, (w, h))
        cam_uint8 = np.uint8(255 * cam_resized)

        colormap = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
        colormap = cv2.cvtColor(colormap, cv2.COLOR_BGR2RGB)

        orig_np = np.array(orig_image)
        blended = np.uint8(orig_np * 0.5 + colormap * 0.5)

        buf = BytesIO()
        Image.fromarray(blended).save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception:
        return None


def assess_image_quality(image: Image.Image) -> dict:
    try:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        
        # Laplacian variance for blurriness
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        is_blurry = lap_var < 60.0
        
        # Mean brightness
        mean_brightness = float(np.mean(gray))
        is_too_dark = mean_brightness < 35.0
        is_too_bright = mean_brightness > 230.0
        
        # Contrast (standard deviation)
        contrast = float(np.std(gray))
        is_low_contrast = contrast < 18.0
        
        w, h = image.size
        is_low_res = (w < 120) or (h < 120)
        
        quality_flags = []
        if is_blurry:
            quality_flags.append("Image appears slightly blurry or out-of-focus. For best results, hold the camera steady.")
        if is_too_dark:
            quality_flags.append("Lighting is very dim / underexposed. Capture in natural daylight.")
        if is_too_bright:
            quality_flags.append("Severe overexposure or direct sunlight glare detected on the leaf.")
        if is_low_contrast:
            quality_flags.append("Low visual contrast between symptomatic leaf and background.")
        if is_low_res:
            quality_flags.append("Resolution is low. Take a closer, high-resolution shot of the leaf.")
            
        return {
            "is_acceptable": len(quality_flags) == 0,
            "blur_score": round(lap_var, 1),
            "is_blurry": is_blurry,
            "brightness_score": round(mean_brightness, 1),
            "lighting": "dark" if is_too_dark else ("glare" if is_too_bright else "optimal"),
            "contrast_score": round(contrast, 1),
            "resolution": f"{w}x{h}",
            "quality_warnings": quality_flags
        }
    except Exception:
        return {"is_acceptable": True, "quality_warnings": []}


def classify_image(image_bytes: bytes) -> dict:
    if not settings.enable_experimental_image_model:
        raise ImageModelUnavailable("Experimental image inference is disabled.")
    if not settings.image_model_path:
        raise ImageModelUnavailable("No image model artifact is configured.")

    model_path = str(settings.resolved_image_model_path)
    with _load_lock:
        torch, model, preprocess, class_names, model_version = _load_model(model_path)
    try:
        with Image.open(BytesIO(image_bytes)) as source:
            image = source.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ValueError("Uploaded content is not a supported image.") from exc

    # Run image quality checks
    quality_report = assess_image_quality(image)

    started = perf_counter()
    tensor = preprocess(image).unsqueeze(0)
    with torch.inference_mode():
        logits = model(tensor)
        scores = torch.softmax(logits, dim=1)[0].tolist()

    ranked = sorted(
        ({"disease_class": name, "uncalibrated_score": float(score)} for name, score in zip(class_names, scores)),
        key=lambda item: item["uncalibrated_score"],
        reverse=True,
    )
    predicted_class = ranked[0]["disease_class"]
    pred_idx = class_names.index(predicted_class)

    # Uncertainty handling
    scores_arr = np.array(scores)
    entropy = float(-np.sum(scores_arr * np.log2(np.clip(scores_arr, 1e-9, 1.0))))
    top_score = ranked[0]["uncalibrated_score"]
    second_score = ranked[1]["uncalibrated_score"] if len(ranked) > 1 else 0.0
    margin = float(top_score - second_score)
    is_uncertain = (top_score < 0.40) or (margin < 0.10) or (entropy > 1.80)
    
    uncertainty_info = {
        "is_uncertain": is_uncertain,
        "predictive_entropy": round(entropy, 3),
        "margin_to_second": round(margin, 3),
        "confidence_level": "high" if top_score >= 0.75 and margin >= 0.35 else ("moderate" if not is_uncertain else "low / uncertain"),
        "reason": (
            f"Close competition between {ranked[0]['disease_class']} and {ranked[1]['disease_class']} (margin {margin*100:.1f}%)."
            if margin < 0.10 else (
                f"Low top-class probability ({top_score*100:.1f}%)." if top_score < 0.40 else None
            )
        )
    }

    # Compute Grad-CAM++ heatmap overlay
    heatmap_b64 = compute_gradcam_overlay(torch, model, preprocess, image, pred_idx)

    return {
        "status": "experimental",
        "predicted_class": predicted_class,
        "uncalibrated_score": ranked[0]["uncalibrated_score"],
        "alternative_predictions": ranked[1:3],
        "class_scores": {name: float(score) for name, score in zip(class_names, scores)},
        "model_version": model_version,
        "processing_time_ms": round((perf_counter() - started) * 1000),
        "explanation": "Grad-CAM++ visual heatmap highlights symptomatic leaf regions that drove the model prediction.",
        "heatmap_base64": heatmap_b64,
        "image_quality": quality_report,
        "uncertainty": uncertainty_info,
        "warning": "Experimental model output from a single public dataset. Scores are uncalibrated; this is not a confirmed diagnosis or field-validated advice.",
        "saved_to_history": False,
    }
