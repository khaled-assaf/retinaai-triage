# AI model

Put training notebooks and scripts here (e.g. `train.ipynb`, `transforms.py`).

**Do not commit datasets or weights.** `data/`, `*.pth`, `*.pt`, `*.onnx`, `*.h5`, `*.ckpt` and
`*.safetensors` are gitignored. Share checkpoints out of band (Drive or a release asset) and
place them at `backend/models/model.pth`.

## Integration point

The backend calls exactly three functions in
[`backend/app/ml/inference.py`](../backend/app/ml/inference.py):

```python
load_model(weights_path) -> model                       # once, at startup
predict(model, img_rgb: np.ndarray) -> {"grade": int, "probabilities": [5 floats]}
gradcam(model, img_rgb: np.ndarray) -> bytes            # PNG heatmap overlay
```

- `img_rgb` is a uint8 `(H, W, 3)` **RGB** array at full resolution that has already passed
  the quality check.
- **Preprocessing in `inference.py` MUST match what the checkpoint was trained with**
  (crop, resize, normalisation, channel order). Ideally keep the transform in a module here
  and import it from both training and inference.
- Install the ML deps with `pip install -r backend/requirements-ml.txt`, set
  `USE_MOCK_MODEL=false` in `backend/.env` and restart. `GET /api/health` → `"mock": false`.
- Bump `REAL_MODEL_VERSION` in `inference.py` whenever you ship new weights.

Dataset suggestion: APTOS 2019 Blindness Detection (5 grades, 0-4). Check its license
before using any images in the demo.
