from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def export_checkpoint(
    pt_path: Path = PROJECT_ROOT / "artifacts" / "image" / "efficientnet_v2_s.pt",
    onnx_path: Path = PROJECT_ROOT / "artifacts" / "image" / "efficientnet_v2_s.onnx",
) -> Path:
    import torch
    from torch import nn
    from torchvision import models

    if not pt_path.is_file():
        raise FileNotFoundError(f"Trained image checkpoint was not found: {pt_path}")
    checkpoint = torch.load(pt_path, map_location="cpu", weights_only=True)
    class_names = checkpoint.get("class_names")
    state_dict = checkpoint.get("state_dict")
    input_size = checkpoint.get("input_size")
    if not isinstance(class_names, list) or not class_names or not isinstance(state_dict, dict):
        raise ValueError("Image checkpoint metadata is invalid.")
    if not isinstance(input_size, int) or input_size < 1:
        raise ValueError("Image checkpoint input size is invalid.")

    model = models.efficientnet_v2_s(weights=None)
    model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(class_names))
    model.load_state_dict(state_dict, strict=True)
    model.eval()

    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    dummy_input = torch.randn(1, 3, input_size, input_size)
    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        export_params=True,
        opset_version=14,
        do_constant_folding=True,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}},
        dynamo=False,
    )

    import onnx

    exported_model = onnx.load(str(onnx_path))
    onnx.checker.check_model(exported_model)
    return onnx_path


if __name__ == "__main__":
    exported = export_checkpoint()
    print(f"Successfully exported on-device ONNX model: {exported.stat().st_size / (1024 * 1024):.2f} MB")
