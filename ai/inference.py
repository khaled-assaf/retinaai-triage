"""RetinaAI DR model — inference adapter for the RetinaAI Nexus backend.

Drop-in for backend/app/ml/inference.py. Self-contained: needs only
numpy, opencv-python(-headless), torch and timm.

    model = load_model("weights/model_inference.pt")   # once, at startup, CPU
    out   = predict(model, img_rgb)                     # {"grade": int, "probabilities": [5 floats]}
    png   = gradcam(model, img_rgb)                     # PNG bytes

Preprocessing is copied 1:1 from the training code (src/retinaai/preprocess.py,
src/retinaai/data.py) and reads its sizes from the checkpoint's saved config.

Thread safety: load_model returns an immutable bundle; predict/gradcam keep all
state in local variables. Grad-CAM takes the gradient w.r.t. the feature map via
torch.autograd.grad (no forward hooks, no parameter .grad writes), so concurrent
calls on the shared model do not interfere. (pytorch-grad-cam is intentionally
NOT used: it registers hooks on the shared model, which is not thread-safe.)

Research/educational prototype only — not for clinical use.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import timm
import torch

GRADE_NAMES = ["No DR", "Mild NPDR", "Moderate NPDR", "Severe NPDR", "Proliferative DR"]
_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)


# --------------------------------------------------------------------------
# Preprocessing — identical to src/retinaai/preprocess.py (validation path)
# --------------------------------------------------------------------------
def _crop_to_fundus(img: np.ndarray, threshold: int = 10) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    mask = gray > threshold
    if mask.mean() < 0.01:
        return img
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    return img[rows[0]: rows[-1] + 1, cols[0]: cols[-1] + 1]


def _pad_to_square(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    s = max(h, w)
    out = np.zeros((s, s, 3), dtype=img.dtype)
    y, x = (s - h) // 2, (s - w) // 2
    out[y: y + h, x: x + w] = img
    return out


def _to_square_fundus(img: np.ndarray, size: int) -> np.ndarray:
    img = _pad_to_square(_crop_to_fundus(img))
    interp = cv2.INTER_AREA if img.shape[0] > size else cv2.INTER_LINEAR
    return cv2.resize(img, (size, size), interpolation=interp)


def _circle_mask(size: int, radius_frac: float) -> np.ndarray:
    mask = np.zeros((size, size), dtype=np.uint8)
    cv2.circle(mask, (size // 2, size // 2), int(size * radius_frac), 1, -1)
    return mask


def _ben_graham(img: np.ndarray) -> np.ndarray:
    size = img.shape[0]
    blur = cv2.GaussianBlur(img, (0, 0), sigmaX=size / 50)
    out = cv2.addWeighted(img, 4, blur, -4, 128)
    mask = _circle_mask(size, 0.48)[..., None]
    return (out * mask + 128 * (1 - mask)).astype(np.uint8)


def _normalize_chw(img: np.ndarray) -> np.ndarray:
    x = img.astype(np.float32) / 255.0
    x = (x - _MEAN) / _STD
    return np.ascontiguousarray(x.transpose(2, 0, 1))


def _check_input(img_rgb: np.ndarray) -> np.ndarray:
    if not isinstance(img_rgb, np.ndarray) or img_rgb.ndim != 3 or img_rgb.shape[2] < 3:
        raise ValueError("img_rgb must be a uint8 numpy array of shape (H, W, 3), RGB order")
    return np.ascontiguousarray(img_rgb[..., :3]).astype(np.uint8, copy=False)


# --------------------------------------------------------------------------
# Model bundle
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class RetinaDRModel:
    net: torch.nn.Module
    img_size: int                 # network input, e.g. 384
    resize_chain: tuple           # e.g. (512, 384): training went original -> 512 -> 384
    enhancement: str              # "ben" or "none"
    tta_flip: bool
    meta: dict                    # epoch, validation metrics (read-only info)

    def square(self, img_rgb: np.ndarray) -> np.ndarray:
        img = img_rgb
        for s in self.resize_chain:
            img = _to_square_fundus(img, s)
        return img

    def tensor(self, square_rgb: np.ndarray) -> torch.Tensor:
        img = _ben_graham(square_rgb) if self.enhancement == "ben" else square_rgb
        return torch.from_numpy(_normalize_chw(img))[None]


def load_model(weights_path: str, tta_flip: bool = False, num_threads: int | None = None) -> RetinaDRModel:
    """Load model_inference.pt on CPU.

    tta_flip=False reproduces the validated metrics exactly (single pass).
    tta_flip=True averages with a horizontal flip (2x CPU time, usually slightly smoother).
    """
    if num_threads:
        torch.set_num_threads(num_threads)
    ckpt = torch.load(weights_path, map_location="cpu", weights_only=True)
    cfg = ckpt["config"]
    n_classes = ckpt.get("heads", {"dr": 5})["dr"]

    net = timm.create_model(cfg["backbone"], pretrained=False, num_classes=n_classes)
    clf = net.pretrained_cfg.get("classifier", "classifier")  # "classifier" for EfficientNet
    state = {}
    for k, v in ckpt["model"].items():
        if k.startswith("backbone."):
            state[k[len("backbone."):]] = v
        elif k.startswith("heads.dr."):
            state[f"{clf}.{k[len('heads.dr.'):]}"] = v
    net.load_state_dict(state, strict=True)
    net.eval()
    for p in net.parameters():
        p.requires_grad_(False)

    chain = (cfg["cache_size"], cfg["img_size"]) if cfg.get("cache_dir") else (cfg["img_size"],)
    meta = {"backbone": cfg["backbone"], "epoch": ckpt.get("epoch", -1) + 1,
            "val_metrics": ckpt.get("metrics", {})}
    return RetinaDRModel(net, cfg["img_size"], chain, cfg.get("preprocess", "ben"), tta_flip, meta)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------
def predict(model: RetinaDRModel, img_rgb: np.ndarray) -> dict:
    x = model.tensor(model.square(_check_input(img_rgb)))
    with torch.inference_mode():
        probs = model.net(x).float().softmax(1)
        if model.tta_flip:
            probs = 0.5 * (probs + model.net(torch.flip(x, dims=[3])).float().softmax(1))
    p = probs[0].numpy().astype(float)
    p = p / p.sum()
    return {"grade": int(p.argmax()), "probabilities": [float(v) for v in p]}


def gradcam(model: RetinaDRModel, img_rgb: np.ndarray, max_width: int = 512,
            alpha: float = 0.4, target: str = "expected_grade") -> bytes:
    """PNG bytes: Grad-CAM heatmap blended over the cropped, squared fundus image.

    target="expected_grade" (default, same as training repo): regions pushing towards MORE
    severe disease. target="predicted": regions supporting the predicted class.
    Layer: output of net.forward_features() == after net.conv_head -> net.bn2 (last conv block).
    """
    img_rgb = _check_input(img_rgb)
    sq = model.square(img_rgb)
    x = model.tensor(sq)
    with torch.enable_grad():
        fmap = model.net.forward_features(x).detach().requires_grad_(True)
        probs = model.net.forward_head(fmap).float().softmax(1)
        if target == "predicted":
            score = probs[0, int(probs.argmax())]
        else:
            score = (probs * torch.arange(probs.shape[1], dtype=probs.dtype)).sum()
        (grad,) = torch.autograd.grad(score, fmap)
    w = grad.mean(dim=(2, 3), keepdim=True)
    cam = torch.relu((w * fmap.detach()).sum(1))[0].numpy()
    cam = cam - cam.min()
    cam = cam / cam.max() if cam.max() > 0 else cam

    # display image: the same crop as the model saw, at <= max_width px, from the full-res original
    disp_size = min(max_width, max(_pad_to_square(_crop_to_fundus(img_rgb)).shape[0], 1))
    disp = _to_square_fundus(img_rgb, disp_size)
    cam = cv2.resize(cam, (disp_size, disp_size), interpolation=cv2.INTER_CUBIC)
    heat = cv2.cvtColor(cv2.applyColorMap((np.clip(cam, 0, 1) * 255).astype(np.uint8),
                                          cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    mask = _circle_mask(disp_size, 0.49)[..., None]
    blended = ((disp * (1 - alpha) + heat * alpha) * mask + disp * (1 - mask)).astype(np.uint8)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(blended, cv2.COLOR_RGB2BGR))
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return buf.tobytes()


if __name__ == "__main__":  # quick manual test: python inference.py weights.pt image.png
    import sys
    import time
    m = load_model(sys.argv[1])
    bgr = cv2.imread(sys.argv[2], cv2.IMREAD_COLOR)
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    t0 = time.perf_counter(); out = predict(m, rgb); t1 = time.perf_counter()
    png = gradcam(m, rgb); t2 = time.perf_counter()
    print(out, GRADE_NAMES[out["grade"]])
    print(f"predict {1000 * (t1 - t0):.0f} ms | gradcam {1000 * (t2 - t1):.0f} ms | png {len(png) / 1024:.0f} KB")
    open("gradcam_test.png", "wb").write(png)
