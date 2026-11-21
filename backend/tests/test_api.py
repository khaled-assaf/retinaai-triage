import cv2

from app.config import get_settings
from app.services.triage import URGENCY_ORDER
from conftest import SAMPLES

CASE_KEYS = {
    "case_id", "created_at", "patient_ref", "quality", "prediction", "heatmap_url", "image_url",
    "triage", "review", "model_version", "processing_ms", "disclaimer", "report_url", "followup",
    "eye", "symptoms", "clinical_status",
}


def upload(client, data, name="eye.jpg", ctype="image/jpeg", **form):
    return client.post("/api/analyze", files={"image": (name, data, ctype)}, data=form)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "model_loaded": True, "mock": True, "model_version": "mock-v0"}


def test_samples_list_and_image(client):
    samples = client.get("/api/samples").json()
    assert {s["id"] for s in samples} >= {"normal", "mild", "moderate", "severe", "blurry"}
    r = client.get(samples[0]["image_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_analyze_upload_full_case(client):
    r = upload(client, (SAMPLES / "severe.jpg").read_bytes(), patient_ref="TEST-1")
    assert r.status_code == 200, r.text
    case = r.json()
    assert set(case) == CASE_KEYS
    assert case["patient_ref"] == "TEST-1"
    assert case["quality"]["passed"] is True
    p = case["prediction"]
    assert 0 <= p["grade"] <= 4 and len(p["probabilities"]) == 5
    assert abs(sum(p["probabilities"]) - 1) < 1e-3
    assert p["confidence"] == max(p["probabilities"])
    assert case["triage"]["level"] in URGENCY_ORDER
    assert case["review"] == {"status": "pending", "clinician_grade": None, "note": None, "reviewed_at": None}
    assert case["clinical_status"] == "pending_review"  # AI suggestion is provisional
    assert case["eye"] == "unknown" and case["symptoms"] == {"collected": False, "reported": []}
    assert case["disclaimer"].startswith("Research prototype")
    for key in ("image_url", "heatmap_url"):
        img = client.get(case[key])
        assert img.status_code == 200
    assert client.get(case["heatmap_url"]).headers["content-type"] == "image/png"
    assert client.get(f"/api/cases/{case['case_id']}/thumbnail").headers["content-type"] == "image/jpeg"


def test_mock_is_deterministic(client):
    a = client.post("/api/samples/moderate/analyze").json()
    b = client.post("/api/samples/moderate/analyze?patient_ref=X").json()
    assert a["case_id"] != b["case_id"]
    assert a["prediction"] == b["prediction"]
    assert a["patient_ref"] == "SAMPLE-moderate" and b["patient_ref"] == "X"


def test_png_upload(client):
    img = cv2.imread(str(SAMPLES / "normal.jpg"))
    ok, buf = cv2.imencode(".png", img)
    r = upload(client, buf.tobytes(), name="eye.png", ctype="image/png")
    assert r.status_code == 200, r.text
    assert client.get(r.json()["image_url"]).headers["content-type"] == "image/png"


def test_blurry_sample_is_retake(client):
    case = client.post("/api/samples/blurry/analyze").json()
    assert case["quality"]["passed"] is False
    assert case["prediction"] is None and case["heatmap_url"] is None
    assert case["triage"]["level"] == "retake"
    assert client.get(f"/api/cases/{case['case_id']}/heatmap").status_code == 404


def test_unsupported_type_400(client):
    r = upload(client, b"GIF89a....", name="x.gif", ctype="image/gif")
    assert r.status_code == 400 and isinstance(r.json()["detail"], str)
    r = upload(client, b"just some text", name="x.jpg")
    assert r.status_code == 400


def test_undecodable_image_400(client):
    r = upload(client, b"\xff\xd8\xff" + b"\x00" * 500)
    assert r.status_code == 400
    assert "decode" in r.json()["detail"].lower()


def test_too_large_413(client):
    settings = get_settings()
    old = settings.max_upload_mb
    settings.max_upload_mb = 0.01  # ~10 KB
    try:
        r = upload(client, (SAMPLES / "normal.jpg").read_bytes())
        assert r.status_code == 413 and "too large" in r.json()["detail"].lower()
    finally:
        settings.max_upload_mb = old


def test_missing_image_has_string_detail(client):
    r = client.post("/api/analyze", data={"patient_ref": "x"})
    assert r.status_code == 422 and isinstance(r.json()["detail"], str)


def test_queue_sorted_and_light(client):
    queue = client.get("/api/queue").json()
    assert len(queue) >= 30  # seeded simulated cases
    ranks = [URGENCY_ORDER.index(c["triage_level"]) for c in queue]
    assert ranks == sorted(ranks)
    levels = {c["triage_level"] for c in queue}
    assert levels >= set(URGENCY_ORDER) - {"emergency"}, levels  # seed covers every AI level
    for c in queue:
        assert c["thumbnail_url"].endswith("/thumbnail")
        assert not any(isinstance(v, str) and len(v) > 300 for v in c.values())  # no base64
    # within a level: priority reviews first, then newest first
    for level in URGENCY_ORDER:
        rows = [c for c in queue if c["triage_level"] == level]
        prio = [c["review_priority"] == "priority" for c in rows]
        assert prio == sorted(prio, reverse=True)
        for flag in (True, False):
            dates = [c["created_at"] for c in rows if (c["review_priority"] == "priority") == flag]
            assert dates == sorted(dates, reverse=True)


def test_case_404(client):
    r = client.get("/api/cases/c_9999")
    assert r.status_code == 404 and r.json() == {"detail": "Case not found"}


def test_patch_review(client):
    cid = client.post("/api/samples/severe/analyze").json()["case_id"]
    r = client.patch(f"/api/cases/{cid}", json={"status": "reviewed", "clinician_grade": 4, "note": "PDR, refer today"})
    assert r.status_code == 200
    review = r.json()["review"]
    assert {k: review[k] for k in ("status", "clinician_grade", "note")} == {
        "status": "reviewed", "clinician_grade": 4, "note": "PDR, refer today"}
    assert review["reviewed_at"]
    assert client.get(f"/api/cases/{cid}").json()["review"]["status"] == "reviewed"
    reviewed = client.get("/api/queue?status=reviewed").json()
    assert cid in {c["case_id"] for c in reviewed}
    assert client.patch(f"/api/cases/{cid}", json={"status": "reviewed", "clinician_grade": 7}).status_code == 422
    assert client.patch("/api/cases/c_9999", json={"status": "reviewed"}).status_code == 404
