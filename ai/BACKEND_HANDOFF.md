# RetinaAI model → RetinaAI Nexus backend: handoff

Model release: **v0.1-baseline** · file `model_inference.pt`
All line numbers refer to the `retinaai-triage` repo. Research/educational prototype only.

> **Short version:** use `export/inference.py` as your `backend/app/ml/inference.py`.
> It is self-contained (numpy, opencv, torch, timm), CPU-only and thread-safe, and its
> preprocessing has been checked **bit-for-bit identical** to the training pipeline.

---

## A. Model & weights

**A1. Architecture.** EfficientNet-B0 (timm) + dropout 0.3 + one linear head with 5 outputs.
Defined in `src/retinaai/model.py:20-29`, with backbone and dropout values from `src/retinaai/config.py:26,28`.
Internally: `timm.create_model("efficientnet_b0", pretrained=False, num_classes=0)` + `nn.Linear(1280, 5)`.
Equivalent plain timm model, which `inference.py` uses:
```python
net = timm.create_model("efficientnet_b0", pretrained=False, num_classes=5)
```
The weights need a key rename to load into it (see A2). Dropout only matters in training, so the two models are identical in `eval()` mode.

**A2. Saving format.** This is a **checkpoint dict**, not a full pickled model (`src/retinaai/train.py:122-129`, file written at `:158`):
```
{"format_version": 1, "model": <state_dict>, "config": {...training config...},
 "heads": {"dr": 5}, "epoch": int, "metrics": {...validation metrics...}}
```
- There's no optimizer in this file (it's only in `last.pt`).
- There's **no `module.` prefix**, because DataParallel wasn't used.
- The state_dict keys are `backbone.*` and `heads.dr.weight` / `heads.dr.bias`.

Loading on CPU, as done in `export/inference.py` → `load_model`:
```python
ckpt = torch.load(path, map_location="cpu", weights_only=True)
state = {k.removeprefix("backbone."): v for k, v in ckpt["model"].items() if k.startswith("backbone.")}
state["classifier.weight"] = ckpt["model"]["heads.dr.weight"]
state["classifier.bias"]   = ckpt["model"]["heads.dr.bias"]
net = timm.create_model("efficientnet_b0", pretrained=False, num_classes=5)
net.load_state_dict(state, strict=True); net.eval()
```

**A3. File, size and versions.** `model_inference.pt`, **16 MB**. Trained on Kaggle with:
**torch 2.11.0 (+cu130) · timm 1.0.30 · opencv 4.14.0 · numpy 2.1.3**.
For the backend: torch ≥ 2.3 and timm ≥ 1.0 should load it, but matching these versions is safest. The CPU-only torch build is fine.

## B. Preprocessing (validation/test path)

**B4. Steps, in order.** The model expects RGB throughout.
1. **Crop black border**: grayscale (RGB→GRAY), keep rows/columns with any pixel > 10, then crop to that bounding box (`src/retinaai/preprocess.py:37-45`).
2. **Pad to square** with black, centred (`preprocess.py:48-54`).
3. **Resize to 512×512**, `INTER_AREA` if downscaling, otherwise `INTER_LINEAR` (`preprocess.py:57-61`). This was the training cache step (`src/retinaai/data.py:43`, saved as lossless PNG).
4. **Repeat steps 1–3 at 384×384** (`data.py:75`). So the model was trained on original → 512 → 384, two resizes. `inference.py` reproduces this from `config.cache_size` and `config.img_size`.
5. **No center crop.**
6. **Ben Graham enhancement**: `blur = GaussianBlur(img, sigma = 384/50 = 7.68)`, then `cv2.addWeighted(img, 4, blur, -4, 128)` (uint8, saturating), then everything outside a circle of radius 0.48·384 is set to 128 (`preprocess.py:70-77`). No CLAHE.
7. **Scale to 0–1** (`/255`) and apply **ImageNet normalisation**: mean (0.485, 0.456, 0.406), std (0.229, 0.224, 0.225) (`preprocess.py:14-15, 88-92`).
8. HWC → CHW, then add a batch dimension. The input tensor is (1, 3, 384, 384) float32.

**B5. Image reading.** Training read images with **OpenCV** and converted BGR→RGB straight away (`preprocess.py:31,34`). The model saw **RGB** only, so your `img_rgb` is exactly the right input.

**B6. Code.** See `export/inference.py`: `_crop_to_fundus`, `_pad_to_square`, `_to_square_fundus`, `_ben_graham`, `_normalize_chw` and `RetinaDRModel.square/tensor`. These are copied from `src/retinaai/preprocess.py`.
They were checked against the real training path (including the cache PNG write/read) on 4 image sizes: **max abs difference = 0.0**.
**End-to-end check on Kaggle (§K2):** running `inference.py` on CPU over 50 validation images reproduced the probabilities saved during training within **0.008** (the remaining difference is because training used GPU half precision), and **50/50 grades matched**.

## C. Output

**C7. Output type.** **5-class softmax classifier**. Trained with `CrossEntropyLoss` (`train.py:98`), using label smoothing 0.05 and sqrt-inverse-frequency class weights (`config.py:38-39`, `data.py:86-90`).
It is not a regression or ordinal model, so there are no thresholds. `grade = argmax(probabilities)`.

**C8. Calibration.** **NOT DONE YET**: no temperature scaling is applied. Two side effects to know about for your confidence < 0.6 rule:
- Label smoothing keeps the top probability below ~0.95, so the model rarely gives very confident outputs.
- Class weights shift some probability toward the rare grades (1, 3, 4).

Expect a noticeable share of images to be flagged "needs clinician review". Temperature scaling can be fitted from the saved validation probabilities (`val_probs.npy`) if needed.

## D. Grad-CAM

**D9. Target layer.** The output of `net.forward_features(x)`, i.e. after `net.conv_head` → `net.bn2` (BN + SiLU), shape (1, 1280, 12, 12).
For pytorch-grad-cam this would be `target_layers=[net.bn2]`, or `[model.backbone.bn2]` in the repo's own model.
`inference.py` does **not** use pytorch-grad-cam. That library registers hooks on the shared model, which isn't thread-safe. Instead it computes the gradient with respect to the feature map using `torch.autograd.grad`, which keeps no shared state.

**D10. Tested?** Yes, on Kaggle through `src/retinaai/explain.py:18-34` (`Predictor.predict` → heatmap was produced).
The default target is the **expected grade** Σk·p_k, which highlights regions pushing toward more severe disease. `gradcam(..., target="predicted")` instead uses the predicted class score.
The heatmap is blended over the cropped, squared fundus at ≤512 px, the same crop the model saw.

## E. Data & results

**E11. Dataset and split.** **APTOS 2019** `train.csv` only (3,662 images). Split is **stratified 80/20** with seed 42 (`data.py:35-37`, `config.py:20,43`): 2,929 train / 733 validation.
There is **no separate test set**. The validation set was also used to pick the best epoch, so the metrics below are slightly optimistic. External validation (e.g. Messidor-2, IDRiD) is **NOT DONE YET**.

**E12. Validation results** (best epoch 9, n = 733):

| | Value |
|---|---|
| Accuracy | 0.821 |
| Quadratic weighted kappa | **0.893** |
| Referable (≥2) AUC | 0.980 |
| Referable sensitivity / specificity (P(≥2) ≥ 0.5) | 0.893 / 0.956 |

Per-class recall: grade 0 **0.97** (350/361) · 1 **0.77** (57/74) · 2 **0.74** (147/200) · 3 **0.41** (16/39) · 4 **0.54** (32/59)

Confusion matrix (rows = true, columns = predicted):
```
        0    1    2    3    4
0     350    9    2    0    0
1       2   57   14    0    1
2       0   30  147   20    3
3       1    1   15   16    6
4       0    5   15    7   32
```
**Urgent cases (grades 3–4, n = 98):**
- 61 (62%) were predicted as 3 or 4.
- 91 (**93%**) were predicted ≥ 2, so they would still be referred.
- **7 (7%) were predicted 0–1**: these are the dangerous misses.
- Of the 85 images predicted 3–4, 61 (72%) were truly 3–4.

The model is weakest at telling grade 3 apart from grade 2.

**E13. Class imbalance.** Handled with class-weighted loss (sqrt inverse frequency), not resampling.
The model is **not biased toward grade 0**: it predicted grade 0 for 353 images vs 361 true, and only 3 non-zero images were called 0. It **over-predicts grade 1** (102 predicted vs 74 true), mostly by calling grade-2 images grade 1.

**E14. Ungradable class.** There is **none**. The model was trained only on APTOS images, which all have a grade from 0 to 4.
It will always output a grade, even for a bad image, so your quality check before the model is essential. The repo also has a heuristic check in `src/retinaai/quality.py`, which also rejects images that aren't fundus photos.

### C9. Review-rate analysis for your triage rule

Rule tested: "needs clinician review" if confidence < threshold **or** top-two gap < 0.15. Validation set, n = 733:

| Confidence threshold | Review rate | Reviewed | Accuracy, auto-accepted | Accuracy, reviewed | Referable cases missed among auto-accepted |
|---|---|---|---|---|---|
| 0.5 | 10.5% | 77 | 85.7% | 51.9% | 27 |
| **0.6** | **17.6%** | **129** | **88.9%** | **50.4%** | **19** |
| 0.7 | 28.6% | 210 | 92.0% | 57.6% | 13 |

What this shows:
- **The rule works for accuracy.** Auto-accepted cases are clearly more accurate than the overall 82%, and the reviewed cases really are the hard ones.
- **It is not enough for safety.** 37 referable (grade ≥ 2) cases are graded 0–1 overall. Even at 0.7, 13 of them pass confidently with no review. Most are grade 2 confidently predicted as grade 1.

**Recommendation:** use **threshold 0.6**, plus a second rule:
`p_referable = sum(probabilities[2:])`, and refer when `p_referable >= T`, **even if the predicted grade is 0–1**.
**T = 0.15**: see C10 (where U = 0.25 is also added for severe cases).

### C10. Safety rules: T (missed referrals) and U (missed urgent cases)

> ⚠️ **All numbers come from the validation set (n = 733)**, which was also used to choose the training epoch. They are **slightly optimistic**, and with groups this small a difference of 1–3 cases is within noise. The quality step was not simulated, so **retake = 0** everywhere. Source: the predictions saved during training (`val_probs.npy`, model sha256 `ce771f11684c3d58…`, the same file the backend has).

**Rule order simulated (first match wins):**
1. quality failed → retake (not simulated)
2. top1 < 0.6 **or** top1 − top2 < 0.15 → **review**
3. **NEW T:** predicted grade 0–1 **and** p_ref = p2+p3+p4 ≥ T → **referable**
4. **NEW U:** predicted grade 2 **and** p_urgent = p3+p4 ≥ U → **urgent**
5. grade 0–1 → routine · grade 2 → referable · grade 3–4 → urgent

The new rules come after the review rule, so they **never change the review rate: it stays 17.6% (129/733) in every row below.**

#### Q1. Referable safety rule, value of T (without U)

Validation set: 298 truly referable (grade ≥ 2), 435 grade 0–1.

| T | Missed referrals (true ≥2 → routine) | of which true grade 2 / 3 / 4 | Unnecessary referrals (true 0–1 → referable/urgent) | of which true grade 0 / 1 | Review rate | All referred (referable + urgent) |
|---|---|---|---|---|---|---|
| no rule (today) | 19 | 16 / 1 / 2 | 12 | 1 / 11 | 17.6% | 25.4% |
| **0.15** | **7** | **6 / 1 / 0** | **35** | **8 / 27** | **17.6%** | **30.2%** |
| 0.20 | 13 | 10 / 1 / 2 | 30 | 6 / 24 | 17.6% | 28.6% |
| 0.25 | 14 | 11 / 1 / 2 | 21 | 3 / 18 | 17.6% | 27.3% |
| 0.30 | 15 | 12 / 1 / 2 | 19 | 2 / 17 | 17.6% | 26.9% |
| 0.35 | 18 | 15 / 1 / 2 | 16 | 2 / 14 | 17.6% | 26.1% |
| 0.40 | 19 | 16 / 1 / 2 | 12 | 1 / 11 | 17.6% | 25.4% |

For reference, lower values (not requested): T = 0.12 → 4 missed / 46 unnecessary; T = 0.10 → 3 / 66; T = 0.05 → 0 / 339 (73% of all patients referred, so not usable).

**Recommendation: T = 0.15.**
- It cuts missed referrals from **19 to 7** and catches **both missed grade-4 cases** (their p_ref was 0.177 and 0.178, just above 0.15). Between 0.20 and 0.40 the rule barely helps.
- The cost is **23 extra referrals** (12 → 35). 27 of the 35 unnecessary referrals are true **grade 1** (mild NPDR, which is not healthy), and only 8 are grade 0, i.e. **2.2% of healthy eyes**. Overall referrals go from 25% to 30%.
- Going below 0.15 gets expensive quickly: removing 3 more misses costs 11 more unnecessary referrals (T = 0.12), and removing 4 costs 31 more (T = 0.10).
- **All 19 original misses were predicted grade 1, never grade 0.** The 7 that remain at T = 0.15 are 6× grade 2 and 1× grade 3. The model gave all of them grade 1 with confidence 0.65–0.95 and p_ref 0.05–0.14. IDs: `282bc792d23a, a804cef3e51f, 4360a112db10 (grade 3), 6e68e742f5bc, a45d77edf8d9, 7d8f67cadc29, e150935f66a6`.
- *Option for the clinical rules (team decision):* because every remaining miss is predicted grade 1, a **shorter rescreen interval for predicted grade 1** than for grade 0 (instead of 365 days for both) would limit the harm of these misses without extra referrals.

#### Q2. Severe cases (grades 3–4) downgraded to referable (90 days)

Of the **98** true grade 3–4 cases:
- With **today's rules**: **16** end up referable (90 d) instead of urgent. The rest: 44 urgent, 35 review, 3 routine.
- With **T = 0.15** added: **18** end up referable. The 2 grade-4 cases that were routine move to referable. The rest: 44 urgent, 35 review, 1 routine.

U rule tested on top of T = 0.15:

| U | True grade 3–4 → urgent (of 98) | True 3–4 → referable (90 d) | True 3–4 → review | True 3–4 → routine | False alarms (true 0–2 → urgent) |
|---|---|---|---|---|---|
| no U rule | 44 | 18 | 35 | 1 | 6 (all grade 2) |
| 0.20 | 55 | 7 | 35 | 1 | 33 (32 grade 2, 1 grade 1) |
| **0.25** | **52** | **10** | **35** | **1** | **21 (all grade 2)** |
| 0.30 | 48 | 14 | 35 | 1 | 17 (all grade 2) |
| 0.35 | 45 | 17 | 35 | 1 | 9 (all grade 2) |
| 0.40 | 44 | 18 | 35 | 1 | 6 (all grade 2) |

**Recommendation: U = 0.25.**
- It moves **8 more severe cases** to urgent (44 → 52), and **87 of 98** are then urgent or in clinician review.
- **Every false alarm at U = 0.25 is a true grade-2 patient.** These patients need a referral anyway, so the only cost is that they're seen in 14 days instead of 90. No grade 0–1 patient becomes urgent.
- Going to U = 0.20 catches 3 more severe cases but adds 12 more false alarms, including one grade-1 patient.

#### Q3. Final triage table (T = 0.15, U = 0.25) vs. today's rules

**With the new rules:**

| True grade | urgent | review | referable | retake | routine | total |
|---|---|---|---|---|---|---|
| 0 | 0 | 6 | 8 | 0 | 347 | 361 |
| 1 | 0 | 18 | 27 | 0 | 29 | 74 |
| 2 | 21 | 70 | 103 | 0 | 6 | 200 |
| 3 | 20 | 15 | 3 | 0 | 1 | 39 |
| 4 | 32 | 20 | 7 | 0 | 0 | 59 |

**Today's rules, without T and U:**

| True grade | urgent | review | referable | retake | routine | total |
|---|---|---|---|---|---|---|
| 0 | 0 | 6 | 1 | 0 | 354 | 361 |
| 1 | 0 | 18 | 11 | 0 | 45 | 74 |
| 2 | 6 | 70 | 108 | 0 | 16 | 200 |
| 3 | 16 | 15 | 7 | 0 | 1 | 39 |
| 4 | 28 | 20 | 9 | 0 | 2 | 59 |

| | Today | With T = 0.15, U = 0.25 |
|---|---|---|
| Missed referrals (true ≥2 → routine) | 19 | **7** |
| Missed urgent (true 3–4 → neither urgent nor review) | 19 | **11** (10 referable, 1 routine) |
| Unnecessary referrals (true 0–1 → referable/urgent) | 12 | 35 |
| Review rate | 17.6% | 17.6% |

**Summary:** missed referrals 19 → 7, missed urgent 19 → 11, unnecessary referrals 12 → 35, review rate unchanged at 17.6%.

#### Q4. Demo images

The 5 PNG files are sent alongside this document (original APTOS resolution, from the validation set). Results under the final rules, from the saved validation predictions:

| File | True grade | Predicted grade | Confidence (top1) | Top1 − top2 | p_ref | p_urgent | Triage today | Triage with T/U |
|---|---|---|---|---|---|---|---|---|
| `13c191b59ed0.png` | 0 | 0 | 0.955 | 0.939 | 0.03 | 0.02 | routine | routine |
| `3ee17aa12e46.png` | 1 | 1 | 0.978 | 0.962 | 0.02 | 0.01 | routine | routine |
| `bfd5c0e55420.png` | 2 | 2 | 0.948 | 0.914 | 0.96 | 0.02 | referable | referable |
| `dbfd238b3468.png` | 3 | 3 | 0.869 | 0.793 | 0.99 | 0.92 | urgent | urgent |
| `27e2be850a99.png` | 4 | 4 | 0.942 | 0.907 | 0.99 | 0.98 | urgent | urgent |

None of the demo images reaches the review threshold, and the new rules don't change any of them. Values come from the GPU-saved predictions; your CPU run may differ by up to ~0.01 (see §B6), which doesn't change any decision here. These are hand-picked correct cases (see G18); the APTOS licence question (G17) is still open.

#### Q5. Changes since v0.1-baseline

**No changes.** `inference.py` and the weights are unchanged (sha256 `ce771f11684c3d58922080f4087ea9643b690e12cb2f14b673773aa5bca4f7a6`), so there's no need to re-integrate. The new rules only use the `probabilities` that `predict()` already returns:
```python
p = out["probabilities"]; grade = out["grade"]
p_ref, p_urgent = sum(p[2:]), sum(p[3:])
# after the review rule, before the grade mapping:
if grade <= 1 and p_ref >= 0.15:    level = "referable"
elif grade == 2 and p_urgent >= 0.25: level = "urgent"
```

## F. Speed

**F15. CPU speed.** **Measured by the backend team** (Intel i7-13650HX, CPU only, median of 10 runs): a full request (decode + quality + predict + Grad-CAM + thumbnail) takes **85 ms at 640×480, 141 ms at 2416×1736 and 179 ms at 3216×2136**. Predict alone takes 30–40 ms, Grad-CAM 50–70 ms, model load 0.7 s, and limiting torch to 2 threads gives the same times. That's well under the "couple of seconds" target. The model is ~16 MB on disk and ~100–200 MB of RAM at runtime.
Measure it with: `python inference.py model_inference.pt some_image.png`, which prints the times.

**F16. TTA / ensemble.** **No ensemble.** `inference.py` runs a **single pass** by default, which is exactly how the validation metrics were computed (`train.py:51-60`).
`load_model(path, tta_flip=True)` adds a horizontal-flip average (2× time); it wasn't validated separately.
The repo's own `Predictor` additionally uses MC-dropout × flip (16 passes) for uncertainty estimates. Your triage doesn't need that.

## G. Licensing & demo images

**G17. License.** **NOT VERIFIED.** APTOS 2019 is Kaggle competition data, with its use governed by the competition rules (Rules tab, "Competition Data" section). Read that section before showing images in a **public** demo. Treat the data as non-commercial research and education only, and credit APTOS / Aravind Eye Hospital.

**G18. Demo images.** These come from the **validation set** (the model never trained on them). Each is predicted correctly and with high confidence. Files are in `train_images/` of APTOS 2019:

| Grade | File | Model confidence |
|---|---|---|
| 0 No DR | `13c191b59ed0.png` | 0.96 |
| 1 Mild NPDR | `3ee17aa12e46.png` | 0.98 |
| 2 Moderate NPDR | `bfd5c0e55420.png` | 0.95 |
| 3 Severe NPDR | `dbfd238b3468.png` | 0.87 |
| 4 Proliferative DR | `27e2be850a99.png` | 0.94 |

These were hand-picked as correct, confident cases. They show how the system works, not how accurate it is. Licensing caveat: see G17.

## H. Deliverables

**H19.** `export/inference.py` provides `load_model`, `predict` and `gradcam` with your signatures. It is CPU-only, runs `eval()` with `inference_mode` (a stricter `no_grad`), keeps no global mutable state, and returns PNG bytes of ≤512 px width.

**H20. Checklist (what you'll receive):**
- [x] `model_inference.pt` (16 MB), via the GitHub Release `v0.1-baseline` or Drive (never committed to git)
- [x] `inference.py` (this repo: `export/inference.py`)
- [x] Versions: torch 2.11.0 · timm 1.0.30 · opencv 4.14.0 · numpy 2.1.3
- [x] §K2 check passed (max difference 0.008, 50/50 grades)
- [x] 5 demo image file names (G18)
- [x] This document
- [x] CPU time measured by backend (F15): 85–179 ms per full request
- [x] Triage safety thresholds: T = 0.15, U = 0.25 (C10)
- [x] Demo PNG files sent (C10 Q4)
- [ ] **Still open:** check the APTOS rules for public display of images (G17)

---

## K. Kaggle cells (run in the training notebook)

**K1: Versions and file size**
```python
import torch, timm, cv2, numpy
print("torch", torch.__version__, "| timm", timm.__version__, "| opencv", cv2.__version__, "| numpy", numpy.__version__)
!ls -lh /kaggle/working/outputs/baseline/model_inference.pt
```

**K2: Check inference.py against the training-time validation predictions**
```python
import sys, numpy as np, pandas as pd, cv2
sys.path.insert(0, "export"); import inference as inf
DATA = "/kaggle/input/competitions/aptos2019-blindness-detection"; RUN = "/kaggle/working/outputs/baseline"
m   = inf.load_model(f"{RUN}/model_inference.pt")
val = pd.read_csv(f"{RUN}/val_split.csv", dtype={"id": str})
ref = np.load(f"{RUN}/val_probs.npy")                     # saved during training, same order as val_split.csv
diffs, agree = [], 0
for i in range(50):
    rgb = cv2.cvtColor(cv2.imread(f"{DATA}/train_images/{val.id[i]}.png"), cv2.COLOR_BGR2RGB)
    out = inf.predict(m, rgb)
    diffs.append(np.abs(np.array(out["probabilities"]) - ref[i]).max()); agree += out["grade"] == ref[i].argmax()
print(f"max prob difference {max(diffs):.4f} (expect < ~0.02: training used GPU half precision) | grade agreement {agree}/50")
open("gradcam_check.png", "wb").write(inf.gradcam(m, rgb))
```

**K3: Demo images (correct and confident, one per grade, validation set only)**
```python
val["pred"], val["conf"] = ref.argmax(1), ref.max(1)
picks = val[val.pred == val.label].sort_values("conf", ascending=False).groupby("label").head(1).sort_values("label")
print(picks[["id", "label", "conf"]].to_string(index=False))
```
