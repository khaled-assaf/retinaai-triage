"""SQLite storage (stdlib sqlite3, no ORM). Images live as files under STORAGE_DIR;
the DB only stores their paths. A new connection per call keeps it thread-safe
for FastAPI's threadpool.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ..config import get_settings
from ..services.triage import URGENCY_ORDER

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id         TEXT UNIQUE,
    created_at      TEXT NOT NULL,
    patient_ref     TEXT,
    quality_json    TEXT NOT NULL,
    prediction_json TEXT,
    triage_level    TEXT NOT NULL,
    triage_json     TEXT NOT NULL,
    review_status   TEXT NOT NULL DEFAULT 'pending',
    clinician_grade INTEGER,
    note            TEXT,
    reviewed_at     TEXT,
    model_version   TEXT NOT NULL,
    processing_ms   INTEGER NOT NULL,
    image_path      TEXT,
    image_mime      TEXT,
    heatmap_path    TEXT,
    thumbnail_path  TEXT
);
CREATE INDEX IF NOT EXISTS idx_cases_level ON cases(triage_level);
"""

_URGENCY_SQL = "CASE triage_level " + " ".join(
    f"WHEN '{level}' THEN {i}" for i, level in enumerate(URGENCY_ORDER)
) + f" ELSE {len(URGENCY_ORDER)} END"


def _db_path() -> Path:
    return get_settings().db_path


def _files_dir() -> Path:
    return get_settings().storage_dir / "cases"


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path(), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    _db_path().parent.mkdir(parents=True, exist_ok=True)
    _files_dir().mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)


def count_cases() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def create_case(
    *,
    patient_ref: Optional[str],
    quality: dict,
    prediction: Optional[dict],
    triage: dict,
    model_version: str,
    processing_ms: int,
    image_bytes: bytes,
    image_ext: str,
    image_mime: str,
    thumbnail_jpg: bytes,
    heatmap_png: Optional[bytes],
) -> dict:
    """Insert a case, write its files, and return the full case dict."""
    files_dir = _files_dir()
    files_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    try:
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO cases (created_at, patient_ref, quality_json, prediction_json,
                       triage_level, triage_json, model_version, processing_ms, image_mime)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now_iso(),
                    patient_ref,
                    json.dumps(quality),
                    json.dumps(prediction) if prediction else None,
                    triage["level"],
                    json.dumps(triage),
                    model_version,
                    processing_ms,
                    image_mime,
                ),
            )
            case_id = f"c_{cur.lastrowid:04d}"

            def write(name: str, data: bytes) -> str:
                path = files_dir / name
                path.write_bytes(data)
                written.append(path)
                return str(path)

            image_path = write(f"{case_id}_image.{image_ext}", image_bytes)
            thumb_path = write(f"{case_id}_thumb.jpg", thumbnail_jpg)
            heatmap_path = write(f"{case_id}_heatmap.png", heatmap_png) if heatmap_png else None
            conn.execute(
                "UPDATE cases SET case_id=?, image_path=?, thumbnail_path=?, heatmap_path=? WHERE id=?",
                (case_id, image_path, thumb_path, heatmap_path, cur.lastrowid),
            )
    except Exception:
        for p in written:
            p.unlink(missing_ok=True)
        raise
    case = get_case(case_id)
    assert case is not None
    return case


def _row(case_id: str) -> Optional[sqlite3.Row]:
    with connect() as conn:
        return conn.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,)).fetchone()


def _to_case(row: sqlite3.Row) -> dict:
    cid = row["case_id"]
    return {
        "case_id": cid,
        "created_at": row["created_at"],
        "patient_ref": row["patient_ref"],
        "quality": json.loads(row["quality_json"]),
        "prediction": json.loads(row["prediction_json"]) if row["prediction_json"] else None,
        "heatmap_url": f"/api/cases/{cid}/heatmap" if row["heatmap_path"] else None,
        "image_url": f"/api/cases/{cid}/image",
        "triage": json.loads(row["triage_json"]),
        "review": {
            "status": row["review_status"],
            "clinician_grade": row["clinician_grade"],
            "note": row["note"],
        },
        "model_version": row["model_version"],
        "processing_ms": row["processing_ms"],
    }


def _to_summary(row: sqlite3.Row) -> dict:
    cid = row["case_id"]
    pred = json.loads(row["prediction_json"]) if row["prediction_json"] else None
    triage = json.loads(row["triage_json"])
    return {
        "case_id": cid,
        "created_at": row["created_at"],
        "patient_ref": row["patient_ref"],
        "triage_level": row["triage_level"],
        "triage_label": triage["label"],
        "grade": pred["grade"] if pred else None,
        "grade_label": pred["label"] if pred else None,
        "confidence": pred["confidence"] if pred else None,
        "quality_passed": json.loads(row["quality_json"])["passed"],
        "review_status": row["review_status"],
        "thumbnail_url": f"/api/cases/{cid}/thumbnail",
    }


def get_case(case_id: str) -> Optional[dict]:
    row = _row(case_id)
    return _to_case(row) if row else None


def list_queue(review_status: Optional[str] = None, limit: int = 200) -> list[dict]:
    sql = "SELECT * FROM cases WHERE case_id IS NOT NULL"
    params: list = []
    if review_status:
        sql += " AND review_status = ?"
        params.append(review_status)
    sql += f" ORDER BY {_URGENCY_SQL}, created_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [_to_summary(r) for r in conn.execute(sql, params).fetchall()]


def update_review(case_id: str, status: str, clinician_grade: Optional[int], note: Optional[str]) -> Optional[dict]:
    with connect() as conn:
        cur = conn.execute(
            "UPDATE cases SET review_status=?, clinician_grade=?, note=?, reviewed_at=? WHERE case_id=?",
            (status, clinician_grade, note, now_iso() if status == "reviewed" else None, case_id),
        )
        if cur.rowcount == 0:
            return None
    return get_case(case_id)


def get_file(case_id: str, kind: str) -> Optional[tuple[str, str]]:
    """Return (path, media_type) for kind in {image, heatmap, thumbnail}."""
    row = _row(case_id)
    if not row:
        return None
    if kind == "image":
        path, mime = row["image_path"], row["image_mime"]
    elif kind == "heatmap":
        path, mime = row["heatmap_path"], "image/png"
    else:
        path, mime = row["thumbnail_path"], "image/jpeg"
    if not path or not Path(path).is_file():
        return None
    return path, mime
