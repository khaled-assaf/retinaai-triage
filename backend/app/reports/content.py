"""What the European Retina Passport says, decided ONCE for all languages.

`build_report()` turns a case record into:
  - `codes`: language-independent decisions (clinical status, TrustGate checks, history
    comparison, which warnings appear, ...). Tests compare these across languages.
  - `text`:  the same decisions rendered as strings in one language (i18n.py).
pdf.py only lays out `text`; it makes no clinical decisions.

Nothing here is invented: missing data is shown as "Not recorded" / "Not assessed".
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional

from ..services.quality import MIN_BLUR_SCORE
from ..services.triage import SAFETY_RULES, TOP2_MIN_MARGIN
from .i18n import LANGUAGES, fmt_date, fmt_datetime, t

MOCK_PREFIX = "mock"


def round_to_100(probs: list[float]) -> list[int]:
    """Integer percentages that add up to exactly 100 (largest-remainder method).
    Display only: the underlying model outputs are never changed."""
    total = sum(probs) or 1.0
    raw = [p / total * 100 for p in probs]
    floors = [math.floor(x) for x in raw]
    missing = 100 - sum(floors)
    order = sorted(range(len(raw)), key=lambda i: (raw[i] - floors[i], raw[i]), reverse=True)
    for i in order[:missing]:
        floors[i] += 1
    return floors


def _quality_reason_codes(quality: dict) -> list[str]:
    checks = quality.get("checks", {})
    out = []
    if checks.get("blur", 1.0) < MIN_BLUR_SCORE:
        out.append("blur")
    if checks.get("exposure", "ok") != "ok":
        out.append(checks["exposure"])
    if checks.get("framing", "ok") != "ok":
        out.append(checks["framing"])
    return out


def _date_part(iso_value: str) -> str:
    return iso_value[:10]


def _order_key(item: dict) -> tuple:
    """Chronological order; the case number breaks ties within the same second."""
    cid = str(item.get("case_id", ""))
    num = int(cid[2:]) if cid.startswith("c_") and cid[2:].isdigit() else 0
    return (item["created_at"], num)


def build_report(
    *,
    case: dict,
    patient: Optional[dict],
    history: list[dict],
    lang: str,
    confidence_threshold: float,
    public: bool = False,
    share_url: Optional[str] = None,
    share_expires_at: Optional[str] = None,
    now: Optional[str] = None,
) -> dict:
    """Decide and word the whole report. `history` = the patient's case summaries."""
    assert lang in LANGUAGES
    tr = lambda key: t(lang, key)  # noqa: E731
    generated = now or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    triage = case["triage"]
    level = triage["level"]
    action_code = triage.get("action_code") or {"urgent": "urgent_grade4"}.get(level, level)
    pred = case.get("prediction")
    ai_grade = pred["grade"] if pred else None
    review = case["review"]
    clinical_status = case.get("clinical_status", "pending_review")
    symptoms = case.get("symptoms") or {"collected": False, "reported": []}
    eye = case.get("eye") or "unknown"
    grades = tr("grades")
    simulated_model = str(case.get("model_version", "")).startswith(MOCK_PREFIX)

    # ------------------------------------------------------------ TrustGate checks
    quality_passed = case["quality"]["passed"]
    tg_quality = "passed" if quality_passed else "failed"

    probs = pred["probabilities"] if pred else None
    flags = []  # why the confidence check flagged the case
    if probs:
        ordered = sorted(probs, reverse=True)
        if ordered[0] < confidence_threshold:
            flags.append("low_conf")
        if ordered[0] - ordered[1] < TOP2_MIN_MARGIN:
            flags.append("close")
        if triage.get("safety_rule") == "referable":
            flags.append("safety_ref")
        if triage.get("safety_rule") == "urgent":
            flags.append("safety_urg")
    tg_conf = "not_assessed" if not probs else ("flagged" if flags else "ok")

    if not symptoms["collected"]:
        tg_sym = "not_collected"
    elif symptoms["reported"]:
        tg_sym = "warning"
    else:
        tg_sym = "none"

    if level == "emergency":
        workflow = "urgent_assessment"
    elif level == "retake":
        workflow = "retake"
    elif clinical_status in ("confirmed", "modified"):
        workflow = "clinician_reviewed"
    elif level == "review":
        workflow = "human_review"
    else:
        workflow = "provisional"

    # ------------------------------------------------------------ result statement
    if level == "emergency":
        result_kind = "emergency"
    elif not quality_passed or pred is None:
        result_kind = "retake"
    elif level == "review" and triage.get("source") != "clinician":
        result_kind = "uncertain"
    else:
        result_kind = f"g{ai_grade}"
    # "No referral suggested" may only appear for a gradable image without warnings,
    # and always as PROVISIONAL until a clinician has reviewed it.
    routine_suggestion = level == "routine"
    provisional = clinical_status == "pending_review"

    # ------------------------------------------------------------ why
    why_codes: list[tuple[str, dict]] = []
    if symptoms["reported"]:
        why_codes.append(("why_symptoms", {"list": ", ".join(tr("symptoms")[s] for s in symptoms["reported"])}))
    if quality_passed:
        why_codes.append(("why_quality_ok", {}))
    else:
        reasons = [tr("quality_reasons")[c] for c in _quality_reason_codes(case["quality"])]
        why_codes.append(("why_quality_fail", {"reasons": "; ".join(reasons) or case["quality"].get("reason", "")}))
    if pred:
        why_codes.append(("why_ai", {"grade": f"{ai_grade} · {grades[ai_grade]}"}))
        top = sorted(probs, reverse=True)
        pct = round_to_100(probs)
        if "low_conf" in flags:
            why_codes.append(("why_low_conf", {"p": max(pct), "t": round(confidence_threshold * 100)}))
        if "close" in flags:
            why_codes.append(("why_close", {"gap": round((top[0] - top[1]) * 100)}))
        if "safety_ref" in flags:
            why_codes.append(("why_safety_ref", {"p": round(sum(probs[2:]) * 100)}))
        if "safety_urg" in flags:
            why_codes.append(("why_safety_urg", {"p": round(sum(probs[3:]) * 100)}))
    if triage.get("source") == "clinician":
        why_codes.append(("why_clinician", {}))
    elif provisional:
        why_codes.append(("why_pending", {}))

    # ------------------------------------------------------------ history
    current_at = case["created_at"]
    previous = sorted(
        (h for h in history if h["case_id"] != case["case_id"] and _order_key(h) < _order_key(case)),
        key=_order_key, reverse=True,
    )
    if not previous:
        hist_status, prev = "none", None
    else:
        prev = previous[0]
        prev_eye = prev.get("eye") or "unknown"
        comparable = (eye != "unknown" and prev_eye == eye and prev.get("grade") is not None and ai_grade is not None)
        if not comparable:
            hist_status = "limited"
        else:
            hist_status = "same" if prev["grade"] == ai_grade else "different"

    # ------------------------------------------------------------ eyes
    same_day_other_eye = eye != "unknown" and any(
        h["case_id"] != case["case_id"] and _date_part(h["created_at"]) == _date_part(current_at)
        and (h.get("eye") or "unknown") not in ("unknown", eye)
        for h in history
    )
    eye_status = "both_eyes" if same_day_other_eye else "single_eye"

    # ------------------------------------------------------------ follow-up
    fu = case.get("followup")

    codes = {
        "level": level,
        "action_code": action_code,
        "clinical_status": clinical_status,
        "provisional": provisional,
        "routine_suggestion": routine_suggestion,
        "result_kind": result_kind,
        "workflow": workflow,
        "trustgate": {"quality": tg_quality, "confidence": tg_conf, "symptoms": tg_sym, "workflow": workflow},
        "why": [c for c, _ in why_codes],
        "history_status": hist_status,
        "eye": eye,
        "eye_status": eye_status,
        "heatmap": "none" if not case.get("heatmap_url") else ("simulated" if simulated_model else "model"),
        "emergency_warning": True,  # always shown, whatever the AI says
        "limits_note": True,        # always shown
        "followup": {k: fu.get(k) for k in ("type", "status", "due_date", "overdue")} if fu else None,
        "public": public,
        "simulated_patient": bool(patient is None or patient.get("simulated", True)),
    }

    # ------------------------------------------------------------ text
    p = patient or {}
    label, action = tr("actions")[action_code]
    if clinical_status == "modified" and review.get("clinician_grade") is not None:
        cg = review["clinician_grade"]
        if ai_grade is not None:
            status_detail = tr("clinician_modified").format(cg=cg, cl=grades[cg], ag=ai_grade, al=grades[ai_grade])
        else:
            status_detail = tr("clinician_modified_no_ai").format(cg=cg, cl=grades[cg])
    elif clinical_status == "confirmed":
        status_detail = tr("clinician_confirmed").format(date=fmt_date(lang, review.get("reviewed_at")))
    elif clinical_status == "pending_review":
        status_detail = tr("provisional")
    else:
        status_detail = ""

    pct = round_to_100(probs) if probs else None
    text = {
        "title": tr("title"),
        "subtitle": tr("subtitle"),
        "language": LANGUAGES[lang],
        "banner": tr("banner_simulated") if codes["simulated_patient"] else tr("banner_prototype"),
        "shared_note": tr("shared_note") if public else "",
        "sections": {k: tr(k) for k in ("sec_a", "sec_b", "sec_c", "sec_d", "sec_e", "sec_f")},
        "patient_rows": [
            (tr("patient_ref"), case.get("patient_ref") or tr("not_recorded")),
            (tr("name"), tr("hidden") if public else (p.get("full_name") or tr("not_recorded"))),
            (tr("birth_year"), tr("hidden") if public else str(p.get("birth_year") or tr("not_recorded"))),
            (tr("diabetes_type"), tr("diabetes_types").get(p.get("diabetes_type"), p.get("diabetes_type")) or tr("not_recorded")),
        ],
        "screening_rows": [
            (tr("exam_date"), fmt_date(lang, case["created_at"])),
            (tr("eye"), tr("eyes")[eye]),
            (tr("image_quality"), tr("passed") if quality_passed else tr("failed")),
            (tr("model"), case.get("model_version", tr("not_recorded"))),
        ],
        "ai_grade_label": tr("ai_grade"),
        "ai_grade": f"{ai_grade} · {grades[ai_grade]}" if pred else tr("no_ai_grade"),
        "top_score": tr("top_score").format(p=max(pct)) if pct else "",
        "triage_label_caption": tr("clinician_triage") if triage.get("source") == "clinician" else tr("ai_triage"),
        "triage_label": label,
        "triage_action": action,
        "clinical_status_caption": tr("clinical_status"),
        "clinical_status": tr("clinical_statuses")[clinical_status],
        "clinical_status_detail": status_detail,
        "result_statement": tr(f"result_{result_kind}"),
        "limits_note": tr("limits_note"),
        "emergency_note": tr("emergency_note"),
        "original_caption": tr("original"),
        "heatmap_caption": tr("heatmap_simulated") if codes["heatmap"] == "simulated" else tr("heatmap"),
        "heatmap_note": tr("heatmap_note") if codes["heatmap"] != "none" else tr("no_heatmap"),
        "scores_caption": tr("scores_caption"),
        "scores": [(f"{i} · {grades[i]}", pct[i], i == ai_grade) for i in range(5)] if pct else [],
        "trustgate": [
            (tr("tg_quality"), {"passed": tr("passed"), "failed": tr("failed")}[tg_quality], tg_quality == "passed"),
            (tr("tg_confidence"), {"ok": tr("tg_conf_ok"), "flagged": tr("tg_conf_flagged"),
                                   "not_assessed": tr("not_assessed")}[tg_conf], tg_conf == "ok"),
            (tr("tg_symptoms"), {"none": tr("tg_sym_none"), "warning": tr("tg_sym_warning"),
                                 "not_collected": tr("tg_sym_not_collected")}[tg_sym], tg_sym == "none"),
            (tr("tg_workflow"), tr("workflow")[workflow], workflow == "clinician_reviewed"),
        ],
        "why_title": tr("why_title"),
        "why": [tr(code).format(**kw) for code, kw in why_codes],
        "thresholds_note": tr("thresholds_note"),
        "followup_caption": tr("followup"),
        "followup_rows": [],
        "history_rows": [],
        "history_header": (tr("date"), tr("case_id"), tr("grade"), tr("triage")),
        "history_compare": [],
        "history_status": {"none": tr("hist_none"), "same": tr("hist_same"), "different": tr("hist_different"),
                           "limited": tr("hist_limited")}[hist_status],
        "history_note": tr("hist_note") if hist_status in ("different", "limited") else "",
        "eye_note": tr(eye_status),
        "footer_trace": " · ".join([
            f"{tr('trace_case')}: {case['case_id']}",
            f"{tr('trace_model')}: {case.get('model_version', '')}",
            f"{tr('trace_generated')}: {fmt_datetime(lang, generated)}",
            f"{tr('trace_review')}: {tr('clinical_statuses')[clinical_status]}",
        ]),
        "disclaimer": tr("disclaimer"),
        "share": tr("share") if share_url else "",
        "share_url": share_url or "",
        "valid_until": f"{tr('valid_until')}: {fmt_date(lang, share_expires_at)}" if share_expires_at else "",
    }
    if fu:
        due = tr("same_day") if fu["type"] == "emergency_assessment" else fmt_date(lang, fu["due_date"])
        status = tr("followup_statuses").get(fu["status"], fu["status"])
        if fu.get("overdue"):
            status += f" · {tr('overdue')}"
        text["followup_rows"] = [
            (tr("fu_type"), tr("followup_types").get(fu["type"], fu["type"])),
            (tr("fu_due"), due),
            (tr("fu_status"), status),
        ]
        if fu.get("appointment_at"):
            text["followup_rows"].append((tr("appointment"), fmt_datetime(lang, fu["appointment_at"])))
    if prev is not None:
        text["history_compare"] = [
            (tr("hist_previous"), f"{prev['grade']} · {grades[prev['grade']]}" if prev.get("grade") is not None
             else tr("none"), fmt_date(lang, prev["created_at"])),
            (tr("hist_current"), f"{ai_grade} · {grades[ai_grade]}" if ai_grade is not None else tr("none"),
             fmt_date(lang, current_at)),
        ]
        for h in previous[:4]:
            g = f"{h['grade']} · {grades[h['grade']]}" if h.get("grade") is not None else tr("none")
            h_code = h.get("action_code") or {"urgent": "urgent_grade4"}.get(h["triage_level"], h["triage_level"])
            text["history_rows"].append((fmt_date(lang, h["created_at"]), h["case_id"], g, tr("actions")[h_code][0]))
    return {"codes": codes, "text": text}


def safety_thresholds() -> dict:
    return {k: v["min_p"] for k, v in SAFETY_RULES.items()}
