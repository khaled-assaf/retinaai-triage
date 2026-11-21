"""European Retina Passport: a multilingual, shareable PDF report for one case.

Built with ReportLab. Uses the bundled Liberation Sans font so every EU alphabet
(ș ț ă, ß, é, ñ, ...) renders correctly.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..services.quality import MIN_BLUR_SCORE
from .i18n import LANGUAGES, fmt_date, t

FONT_DIR = Path(__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "LiberationSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "LiberationSans-Bold.ttf")))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")

BRAND = colors.HexColor("#0B5563")
MUTED = colors.HexColor("#5F6B73")
LIGHT = colors.HexColor("#EEF3F5")
LEVEL_COLORS = {
    "urgent": (colors.HexColor("#B71C1C"), colors.white),
    "review": (colors.HexColor("#E65100"), colors.white),
    "referable": (colors.HexColor("#F9A825"), colors.HexColor("#212121")),
    "retake": (colors.HexColor("#546E7A"), colors.white),
    "routine": (colors.HexColor("#2E7D32"), colors.white),
}

PAGE_W, PAGE_H = A4
MARGIN = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "body": ParagraphStyle("body", fontName="Sans", fontSize=9.5, leading=12.5),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=8, leading=10, textColor=MUTED),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=11.5, leading=14, textColor=BRAND, spaceBefore=8, spaceAfter=4),
    "label": ParagraphStyle("label", fontName="Sans", fontSize=8, leading=10, textColor=MUTED),
    "value": ParagraphStyle("value", fontName="Sans-Bold", fontSize=9.5, leading=12),
    "banner": ParagraphStyle("banner", fontName="Sans-Bold", fontSize=8.5, leading=11, textColor=colors.HexColor("#8A4B00"), alignment=TA_LEFT),
}


def _p(text, style="body", **kw) -> Paragraph:
    text = "" if text is None else str(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, ParagraphStyle(f"{style}-x", parent=S[style], **kw) if kw else S[style])


def _kv_table(rows: list[tuple[str, str]], width: float) -> Table:
    data = [[_p(k, "label"), _p(v, "value")] for k, v in rows]
    tbl = Table(data, colWidths=[width * 0.42, width * 0.58])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


def _image(path: Optional[str], max_w: float, max_h: float, max_px: int = 520):
    """Embed a downscaled JPEG copy (keeps the PDF small)."""
    if not path or not Path(path).is_file():
        return None
    with PILImage.open(path) as im:
        im = im.convert("RGB")
        im.thumbnail((max_px, max_px))
        w, h = im.size
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    buf.seek(0)
    scale = min(max_w / w, max_h / h)
    return Image(buf, width=w * scale, height=h * scale)


def _prob_bars(lang: str, probs: list[float], grade: int, width: float) -> Drawing:
    labels = t(lang, "grades")
    row_h, label_w, bar_w = 13, width * 0.42, width * 0.45
    d = Drawing(width, row_h * 5)
    for i, p in enumerate(probs):
        y = row_h * (4 - i) + 2
        d.add(String(0, y + 1, f"{i} · {labels[i]}", fontName="Sans-Bold" if i == grade else "Sans", fontSize=8))
        d.add(Rect(label_w, y, bar_w, 8, fillColor=LIGHT, strokeColor=None))
        d.add(Rect(label_w, y, max(0.5, bar_w * p), 8, fillColor=BRAND if i == grade else colors.HexColor("#9FB8BF"), strokeColor=None))
        d.add(String(label_w + bar_w + 4, y + 1, f"{p * 100:.0f}%", fontName="Sans", fontSize=8))
    return d


def _qr(url: str, size: float) -> Drawing:
    widget = QrCodeWidget(url)
    x1, y1, x2, y2 = widget.getBounds()
    d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    d.add(widget)
    return d


def _quality_text(lang: str, quality: dict) -> str:
    if quality["passed"]:
        return t(lang, "passed")
    reasons = t(lang, "quality_reasons")
    checks = quality["checks"]
    parts = []
    if checks["blur"] < MIN_BLUR_SCORE:
        parts.append(reasons["blur"])
    if checks["exposure"] != "ok":
        parts.append(reasons[checks["exposure"]])
    if checks["framing"] != "ok":
        parts.append(reasons[checks["framing"]])
    return f"{t(lang, 'failed')}: " + "; ".join(parts or [quality["reason"]])


def build_passport_pdf(
    *,
    case: dict,
    patient: Optional[dict],
    history: list[dict],
    image_path: Optional[str],
    heatmap_path: Optional[str],
    lang: str,
    share_url: Optional[str] = None,
    share_expires_at: Optional[str] = None,
) -> bytes:
    """Render the passport for one case and return the PDF bytes."""
    buf = io.BytesIO()
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=30 * mm, bottomMargin=20 * mm,
        title=f"{t(lang, 'title')} · {case['case_id']}", author="RetinaAI Nexus", subject=t(lang, "subtitle"),
    )

    def decorate(canvas, doc_):
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, PAGE_H - 22 * mm, PAGE_W, 22 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Sans-Bold", 16)
        canvas.drawString(MARGIN, PAGE_H - 12 * mm, t(lang, "title"))
        canvas.setFont("Sans", 9)
        canvas.drawString(MARGIN, PAGE_H - 17.5 * mm, t(lang, "subtitle"))
        canvas.setFont("Sans-Bold", 10)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 12 * mm, "RetinaAI Nexus")
        canvas.setFont("Sans", 8.5)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 17.5 * mm, f"{LANGUAGES[lang]} · {case['case_id']}")
        canvas.setFillColor(MUTED)
        canvas.setFont("Sans", 7.5)
        canvas.drawString(MARGIN, 12 * mm, t(lang, "disclaimer")[:150])
        canvas.drawString(MARGIN, 8 * mm, f"{t(lang, 'generated')}: {fmt_date(lang, generated)} · {t(lang, 'model')}: {case['model_version']}")
        canvas.drawRightString(PAGE_W - MARGIN, 8 * mm, str(doc_.page))
        canvas.restoreState()

    story: list = []
    if patient is None or patient.get("simulated", True):
        banner = Table([[_p(t(lang, "simulated"), "banner")]], colWidths=[CONTENT_W])
        banner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF3E0")),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#FFB74D")),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story += [banner, Spacer(1, 6)]

    # --- patient + screening, side by side
    half = CONTENT_W / 2 - 4 * mm
    p = patient or {}
    patient_rows = [
        (t(lang, "name"), p.get("full_name") or t(lang, "none")),
        (t(lang, "patient_ref"), case.get("patient_ref") or t(lang, "none")),
        (t(lang, "birth_year"), p.get("birth_year") or t(lang, "none")),
        (t(lang, "country"), p.get("country") or t(lang, "none")),
        (t(lang, "diabetes_type"),
         t(lang, "diabetes_types").get(p.get("diabetes_type"), p.get("diabetes_type")) or t(lang, "none")),
    ]
    pred = case.get("prediction")
    screening_rows = [
        (t(lang, "date"), fmt_date(lang, case["created_at"])),
        (t(lang, "case_id"), case["case_id"]),
        (t(lang, "quality"), _quality_text(lang, case["quality"])),
    ]
    if pred:
        screening_rows += [
            (t(lang, "grade"), f"{pred['grade']} · {t(lang, 'grades')[pred['grade']]}"),
            (t(lang, "confidence"), f"{pred['confidence'] * 100:.0f}%"),
        ]
    if share_url:
        # Three columns: patient | screening | QR code for the public link.
        qr_w = 34 * mm
        col = (CONTENT_W - qr_w) / 2 - 3 * mm
        qr_cell = [_qr(share_url, 28 * mm), _p(t(lang, "share"), "small")]
        if share_expires_at:
            qr_cell.append(_p(f"{t(lang, 'valid_until')}: {fmt_date(lang, share_expires_at)}", "small"))
        top = Table(
            [[_p(t(lang, "patient"), "h2"), _p(t(lang, "screening"), "h2"), ""],
             [_kv_table(patient_rows, col), _kv_table(screening_rows, col), qr_cell]],
            colWidths=[col + 6 * mm, col, qr_w],
        )
    else:
        top = Table(
            [[_p(t(lang, "patient"), "h2"), _p(t(lang, "screening"), "h2")],
             [_kv_table(patient_rows, half), _kv_table(screening_rows, half)]],
            colWidths=[half + 8 * mm, half],
        )
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(top)

    # --- triage box
    triage = case["triage"]
    level = triage["level"]
    bg, fg = LEVEL_COLORS.get(level, (BRAND, colors.white))
    label, action = t(lang, "triage_levels")[level]
    lines = [_p(f"{t(lang, 'triage')}: {label}", "value", textColor=fg, fontSize=12.5, leading=16),
             _p(f"{t(lang, 'action')}: {action}", "body", textColor=fg)]
    if triage.get("source") == "clinician":
        lines.append(_p(t(lang, "clinician_override"), "body", textColor=fg))
    elif level == "review":
        lines.append(_p(t(lang, "uncertain"), "body", textColor=fg))
    box = Table([[lines]], colWidths=[CONTENT_W])
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [Spacer(1, 8), box]

    # --- images + probabilities
    img_w = CONTENT_W / 2 - 3 * mm
    original = _image(image_path, img_w, 54 * mm)
    heat = _image(heatmap_path, img_w, 54 * mm)
    cells = [[_p(t(lang, "original"), "label"), _p(t(lang, "heatmap"), "label")],
             [original or "", heat or _p(t(lang, "no_heatmap"), "small")]]
    imgs = Table(cells, colWidths=[CONTENT_W / 2, CONTENT_W / 2])
    imgs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    block = [_p(t(lang, "images"), "h2"), imgs]
    if heat:
        block.append(_p(t(lang, "heatmap_note"), "small"))
    story.append(KeepTogether(block))
    if pred:
        story.append(KeepTogether([_p(t(lang, "probabilities"), "h2"), _prob_bars(lang, pred["probabilities"], pred["grade"], CONTENT_W)]))

    # --- follow-up + clinician review
    fu = case.get("followup")
    half_rows = []
    if fu:
        status = t(lang, "followup_statuses").get(fu["status"], fu["status"])
        if fu.get("overdue"):
            status += f" · {t(lang, 'overdue')}"
        half_rows = [
            (t(lang, "type"), t(lang, "followup_types").get(fu["type"], fu["type"])),
            (t(lang, "due_date"), fmt_date(lang, fu["due_date"])),
            (t(lang, "status"), status),
            (t(lang, "appointment"), fmt_date(lang, fu.get("appointment_at"))),
        ]
    review = case["review"]
    review_rows = [
        (t(lang, "status"), t(lang, "review_statuses").get(review["status"], review["status"])),
        (t(lang, "clinician_grade"),
         f"{review['clinician_grade']} · {t(lang, 'grades')[review['clinician_grade']]}"
         if review.get("clinician_grade") is not None else t(lang, "none")),
        (t(lang, "note"), review.get("note") or t(lang, "none")),
    ]
    mid = Table(
        [[_p(t(lang, "followup"), "h2"), _p(t(lang, "review"), "h2")],
         [_kv_table(half_rows, half) if half_rows else _p(t(lang, "none")), _kv_table(review_rows, half)]],
        colWidths=[half + 8 * mm, half],
    )
    mid.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether(mid))

    # --- history
    past = [h for h in history if h["case_id"] != case["case_id"]]
    hist_block = [_p(t(lang, "history"), "h2")]
    if past:
        rows = [[_p(t(lang, "date"), "label"), _p(t(lang, "case_id"), "label"),
                 _p(t(lang, "grade"), "label"), _p(t(lang, "triage"), "label")]]
        for h in past[:8]:
            grade = f"{h['grade']} · {t(lang, 'grades')[h['grade']]}" if h.get("grade") is not None else t(lang, "none")
            rows.append([_p(fmt_date(lang, h["created_at"])), _p(h["case_id"]), _p(grade),
                         _p(t(lang, "triage_levels")[h["triage_level"]][0])])
        ht = Table(rows, colWidths=[CONTENT_W * 0.17, CONTENT_W * 0.15, CONTENT_W * 0.33, CONTENT_W * 0.35])
        ht.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, MUTED),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ]))
        hist_block.append(ht)
    else:
        hist_block.append(_p(t(lang, "no_history"), "small"))
    story.append(KeepTogether(hist_block))

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
