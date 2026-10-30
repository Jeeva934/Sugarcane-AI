import torch
from pathlib import Path
from torchvision import models
from torch import nn

pt_path = Path("artifacts/image/efficientnet_v2_s.pt")
onnx_path = Path("artifacts/image/efficientnet_v2_s.onnx")

print("Loading checkpoint from:", pt_path)
checkpoint = torch.load(pt_path, map_location="cpu", weights_only=True)
class_names = checkpoint["class_names"]
input_size = checkpoint.get("input_size", 224)

model = models.efficientnet_v2_s(weights=None)
model.classifier[-1] = nn.Linear(model.classifier[-1].in_features, len(class_names))
model.load_state_dict(checkpoint["state_dict"])
model.eval()

dummy_input = torch.randn(1, 3, input_size, input_size)
print(f"Exporting to ONNX: {onnx_path} (input: {dummy_input.shape})...")

torch.onnx.export(
    model,
    dummy_input,
    str(onnx_path),
    export_params=True,
    opset_version=14,
    do_constant_folding=True,
    input_names=["input"],
    output_names=["output"],
    dynamic_axes={"input": {0: "batch_size"}, "output": {0: "batch_size"}}
)

print(f"Successfully exported on-device ONNX model: {onnx_path.stat().st_size / (1024*1024):.2f} MB")

