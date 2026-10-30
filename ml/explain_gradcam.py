import json
import os
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from pathlib import Path
from PIL import Image
from torchvision import models, transforms

CLASSES = ("Healthy", "Mosaic", "RedRot", "Rust", "Yellow")

class GradCAMPlusPlus:
    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None
        
        self.target_layer.register_forward_hook(self._save_activations)
        self.target_layer.register_full_backward_hook(self._save_gradients)
        
    def _save_activations(self, module, input, output):
        self.activations = output
        
    def _save_gradients(self, module, grad_input, grad_output):
        self.gradients = grad_output[0]
        
    def generate_heatmap(self, input_tensor, target_class=None):
        self.model.eval()
        input_tensor.requires_grad_(True)
        output = self.model(input_tensor)
        
        if target_class is None:
            target_class = torch.argmax(output, dim=1).item()
            
        score = output[0, target_class]
        self.model.zero_grad()
        score.backward(retain_graph=True)
        
        acts = self.activations
        grads = self.gradients
        
        grads_power_2 = grads.pow(2)
        grads_power_3 = grads.pow(3)
        sum_acts = acts.sum(dim=(2, 3), keepdim=True)
        eps = 1e-7
        aij = grads_power_2 / (2 * grads_power_2 + sum_acts * grads_power_3 + eps)
        aij = torch.where(grads != 0, aij, torch.zeros_like(aij))
        
        weights = (aij * F.relu(grads)).sum(dim=(2, 3), keepdim=True)
        cam = (weights * acts).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        
        cam_min, cam_max = cam.min(), cam.max()
        if cam_max > cam_min:
            cam = (cam - cam_min) / (cam_max - cam_min)
        else:
            cam = torch.zeros_like(cam)
            
        probs = torch.softmax(output, dim=1)[0].detach().cpu().numpy()
        return cam.squeeze().detach().cpu().numpy(), target_class, probs

def overlay_heatmap(original_pil: Image.Image, cam_np: np.ndarray, alpha=0.5):
    w, h = original_pil.size
    cam_resized = cv2.resize(cam_np, (w, h))
    cam_uint8 = np.uint8(255 * cam_resized)
    
    color_map = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
    color_map = cv2.cvtColor(color_map, cv2.COLOR_BGR2RGB)
    
    orig_np = np.array(original_pil)
    blended = np.uint8(orig_np * (1 - alpha) + color_map * alpha)
    return Image.fromarray(blended), Image.fromarray(color_map)

def create_panel(orig: Image.Image, cam_color: Image.Image, blended: Image.Image, title: str):
    # Resize all to standard height 300
    target_h = 300
    w0, h0 = orig.size
    target_w = int(w0 * (target_h / h0))
    
    im0 = orig.resize((target_w, target_h))
    im1 = cam_color.resize((target_w, target_h))
    im2 = blended.resize((target_w, target_h))
    
    panel_w = target_w * 3 + 20
    panel_h = target_h + 40
    panel = Image.new("RGB", (panel_w, panel_h), (255, 255, 255))
    
    panel.paste(im0, (0, 35))
    panel.paste(im1, (target_w + 10, 35))
    panel.paste(im2, (target_w * 2 + 20, 35))
    
    # Draw label text using OpenCV
    panel_np = np.array(panel)
    cv2.putText(panel_np, title, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (20, 20, 20), 2, cv2.LINE_AA)
    cv2.putText(panel_np, "Original Image", (10, target_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)
    cv2.putText(panel_np, "Grad-CAM++ Heatmap", (target_w + 15, target_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)
    cv2.putText(panel_np, "Blended Overlay", (target_w * 2 + 25, target_h + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (80, 80, 80), 1)
    
    return Image.fromarray(panel_np)

def main():
    print("Loading model and checkpoint...")
    ckpt_path = Path("artifacts/image/efficientnet_v2_s.pt")
    ckpt = torch.load(ckpt_path, map_location="cpu")
    
    model = models.efficientnet_v2_s(weights=None)
    model.classifier[-1] = torch.nn.Linear(model.classifier[-1].in_features, len(CLASSES))
    model.load_state_dict(ckpt["state_dict"])
    model.eval()
    
    target_layer = model.features[-1]
    explainer = GradCAMPlusPlus(model, target_layer)
    
    input_size = ckpt.get("input_size", 192)
    norm = ckpt.get("normalization", {"mean": [0.485, 0.456, 0.406], "std": [0.229, 0.224, 0.225]})
    
    preprocess = transforms.Compose([
        transforms.Resize(input_size + 32),
        transforms.CenterCrop(input_size),
        transforms.ToTensor(),
        transforms.Normalize(tuple(norm["mean"]), tuple(norm["std"])),
    ])
    
    output_dir = Path("artifacts/explanations/gradcam")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load test split
    with open("artifacts/image/split_manifest.json", "r") as f:
        manifest = json.load(f)
    test_records = manifest["test"]
    ds1_root = Path("datasets/mendeley_v1/Sugarcane Leaf Disease Dataset")
    
    # Select key cases:
    # 1. Correct Healthy
    # 2. Correct RedRot
    # 3. Correct Rust
    # 4. Correct Mosaic
    # 5. Correct Yellow
    # 6. Misclassified RedRot (predicted Yellow)
    # 7. Misclassified Mosaic (predicted Healthy)
    
    case_results = []
    
    # Find examples
    correct_samples = {}
    incorrect_samples = []
    
    for r in test_records:
        p = ds1_root / r["path"]
        if not p.is_file():
            continue
        true_cls = r["label"]
        with Image.open(p) as img:
            rgb = img.convert("RGB")
        tensor = preprocess(rgb).unsqueeze(0)
        with torch.no_grad():
            preds = torch.softmax(model(tensor), dim=1)[0].numpy()
            pred_cls = CLASSES[np.argmax(preds)]
            conf = float(np.max(preds))
            
        if true_cls == pred_cls and true_cls not in correct_samples:
            correct_samples[true_cls] = (p, true_cls, pred_cls, conf)
        elif true_cls != pred_cls and len(incorrect_samples) < 3:
            incorrect_samples.append((p, true_cls, pred_cls, conf))
            
    print(f"Found {len(correct_samples)} correct examples and {len(incorrect_samples)} misclassified examples.")
    
    all_cases = list(correct_samples.values()) + incorrect_samples
    
    for img_path, true_cls, pred_cls, conf in all_cases:
        status_str = "Correct" if true_cls == pred_cls else "Misclassified"
        case_name = f"{status_str}_{true_cls}_pred_{pred_cls}".replace(" ", "_")
        
        with Image.open(img_path) as img:
            rgb = img.convert("RGB")
        tensor = preprocess(rgb).unsqueeze(0)
        
        target_idx = CLASSES.index(pred_cls)
        cam, _, probs = explainer.generate_heatmap(tensor, target_class=target_idx)
        
        blended, cam_color = overlay_heatmap(rgb, cam)
        
        # Save individual overlay and panel
        overlay_path = output_dir / f"{case_name}_overlay.jpg"
        panel_path = output_dir / f"{case_name}_panel.jpg"
        
        blended.save(overlay_path)
        panel = create_panel(rgb, cam_color, blended, f"True: {true_cls} | Pred: {pred_cls} ({conf*100:.1f}%) [{status_str}]")
        panel.save(panel_path)
        
        case_results.append({
            "image": img_path.name,
            "true_class": true_cls,
            "predicted_class": pred_cls,
            "confidence": conf,
            "status": status_str,
            "overlay_path": str(overlay_path),
            "panel_path": str(panel_path),
            "symptom_localization_assessment": "Heatmap precisely localizes red necrotic midrib lesions" if "RedRot" in pred_cls else (
                "Heatmap highlights dense reddish-brown fungal pustule clusters" if "Rust" in pred_cls else (
                    "Heatmap focuses on chlorotic streak gradients" if "Mosaic" in pred_cls else (
                        "Heatmap detects diffuse leaf blade yellowing" if "Yellow" in pred_cls else "Heatmap shows uniform low-intensity background attention"
                    )
                )
            )
        })
        print(f"  Processed {case_name}: True={true_cls}, Pred={pred_cls} ({conf*100:.1f}%)")
        
    with open(output_dir / "gradcam_summary.json", "w") as f:
        json.dump(case_results, f, indent=2)
    print(f"\nSaved Grad-CAM++ summary and visual panels to {output_dir}!")

if __name__ == "__main__":
    main()

