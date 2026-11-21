"""Inference: one call -> full result dict (grade, uncertainty, quality, triage, heatmap).

    from retinaai.predict import Predictor
    p = Predictor("weights/model_inference.pt")
    result = p.predict("fundus.png")          # path, bytes, PIL image or RGB array

CLI:
    python -m retinaai.predict --checkpoint weights/model_inference.pt --image fundus.png
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import torch

from .explain import grad_cam, overlay, to_png_base64
from .model import enable_mc_dropout, load_inference_model
from .preprocess import enhance, load_rgb, normalize_chw, to_square_fundus
from .quality import assess_quality
from .result import build_result


class Predictor:
    def __init__(self, checkpoint: str, device: str | None = None,
                 mc_samples: int = 8, tta: bool = True):
        self.device = torch.device(device or ("cuda" if torch.cuda.is_available() else "cpu"))
        self.model, ckpt = load_inference_model(checkpoint, self.device)
        cfg = ckpt["config"]
        self.img_size = cfg["img_size"]
        self.preprocess = cfg["preprocess"]
        self.cache_size = cfg.get("cache_size") if cfg.get("cache_dir") else None
        self.mc_samples = max(1, mc_samples)
        self.tta = tta
        self.model_info = {
            "backbone": cfg["backbone"], "img_size": self.img_size,
            "trained_epoch": ckpt.get("epoch", -1) + 1,
            "val_metrics": {k: v for k, v in ckpt.get("metrics", {}).items()
                            if k in ("qwk", "referable_sensitivity", "referable_specificity",
                                     "referable_auc", "n")},
        }

    def _square(self, rgb: np.ndarray) -> np.ndarray:
        # Must mirror training: with a cache, images went original -> cache_size -> img_size
        # (data.py ensure_cache + FundusDataset.__getitem__).
        if self.cache_size:
            rgb = to_square_fundus(rgb, self.cache_size)
        return to_square_fundus(rgb, self.img_size)

    def _tensor(self, rgb_square: np.ndarray) -> torch.Tensor:
        x = normalize_chw(enhance(rgb_square, self.preprocess))
        return torch.from_numpy(x)[None].to(self.device)

    @torch.no_grad()
    def _mc_probs(self, x: torch.Tensor) -> np.ndarray:
        views = [x, torch.flip(x, dims=[3])] if self.tta else [x]
        enable_mc_dropout(self.model)
        samples = []
        for v in views:
            batch = v.repeat(self.mc_samples, 1, 1, 1)
            samples.append(self.model(batch)["dr"].float().softmax(1).cpu().numpy())
        self.model.eval()
        return np.concatenate(samples)  # (n_samples, 5)

    def predict(self, image, return_heatmap: bool = True) -> dict:
        rgb = load_rgb(image)
        quality = assess_quality(rgb)
        square = self._square(rgb)
        x = self._tensor(square)

        samples = self._mc_probs(x)
        probs = samples.mean(0)
        p_ref_std = float(samples[:, 2:].sum(1).std())

        heatmap = None
        if return_heatmap:
            heatmap = to_png_base64(overlay(square, grad_cam(self.model, x)))
        return build_result(probs, quality, p_ref_std, heatmap, self.model_info)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--heatmap_out", default=None, help="optional path to save heatmap PNG")
    args = ap.parse_args()
    res = Predictor(args.checkpoint).predict(args.image, return_heatmap=True)
    if args.heatmap_out and res["heatmap_png_base64"]:
        import base64
        with open(args.heatmap_out, "wb") as f:
            f.write(base64.b64decode(res["heatmap_png_base64"]))
    res["heatmap_png_base64"] = "<omitted>" if res["heatmap_png_base64"] else None
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
