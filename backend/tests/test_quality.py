import cv2
import numpy as np
import pytest

from app.services.quality import assess_quality
from conftest import SAMPLES


def load_rgb(name):
    img = cv2.imread(str(SAMPLES / name), cv2.IMREAD_COLOR)
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


@pytest.fixture
def sharp():
    return load_rgb("normal.jpg")


def test_sharp_image_passes(sharp):
    q = assess_quality(sharp)
    assert q["passed"], q
    assert q["reason"] == "OK"
    assert q["checks"] == {"blur": q["checks"]["blur"], "exposure": "ok", "framing": "ok"}
    assert q["checks"]["blur"] > 0.6


def test_blurred_image_fails_on_blur(sharp):
    blurred = cv2.GaussianBlur(sharp, (0, 0), 7)
    q_sharp, q_blur = assess_quality(sharp), assess_quality(blurred)
    assert q_blur["checks"]["blur"] < q_sharp["checks"]["blur"]
    assert not q_blur["passed"]
    assert "blurry" in q_blur["reason"].lower()


def test_blurry_sample_fails():
    assert not assess_quality(load_rgb("blurry.jpg"))["passed"]


def test_score_independent_of_resolution(sharp):
    big = cv2.resize(sharp, (1536, 1536), interpolation=cv2.INTER_CUBIC)
    assert assess_quality(big)["passed"]


def test_underexposed(sharp):
    q = assess_quality((sharp * 0.18).astype(np.uint8))
    assert q["checks"]["exposure"] == "underexposed"
    assert not q["passed"]


def test_overexposed(sharp):
    q = assess_quality(np.clip(sharp.astype(np.int32) + 170, 0, 255).astype(np.uint8))
    assert q["checks"]["exposure"] == "overexposed"
    assert not q["passed"]


def test_black_image_has_no_retina():
    q = assess_quality(np.zeros((600, 600, 3), np.uint8))
    assert q["checks"]["framing"] == "not_found"
    assert not q["passed"]


def test_small_retina_is_flagged(sharp):
    canvas = np.zeros((1600, 1600, 3), np.uint8)
    canvas[600:984, 600:984] = cv2.resize(sharp, (384, 384))
    q = assess_quality(canvas)
    assert q["checks"]["framing"] == "too_small"


def test_non_fundus_rectangle_photo(sharp):
    # A regular bright photo with no black border is not a circular fundus region.
    rng = np.random.default_rng(0)
    photo = rng.integers(60, 200, (480, 640, 3), dtype=np.uint8)
    assert assess_quality(photo)["checks"]["framing"] == "not_found"
