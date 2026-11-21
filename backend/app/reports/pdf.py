"""European Retina Passport: layout only.

All clinical decisions and wording come from content.build_report(); this module just
draws them (ReportLab, bundled Liberation Sans for every EU alphabet incl. ș ț ă).
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import Optional

from PIL import Image as PILImage
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing, Rect
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .content import build_report

FONT_DIR = Path(__file__).resolve().parent / "fonts"
pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "LiberationSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "LiberationSans-Bold.ttf")))
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold", italic="Sans", boldItalic="Sans-Bold")

BRAND = colors.HexColor("#0B5563")
BRAND_LIGHT = colors.HexColor("#E6F1F3")
MUTED = colors.HexColor("#5F6B73")
LINE = colors.HexColor("#D5DEE2")
OK = colors.HexColor("#2E7D32")
WARN = colors.HexColor("#B26A00")
LEVEL_COLORS = {
    "emergency": (colors.HexColor("#7F0000"), colors.white),
    "urgent": (colors.HexColor("#B71C1C"), colors.white),
    "review": (colors.HexColor("#E65100"), colors.white),
    "referable": (colors.HexColor("#F9A825"), colors.HexColor("#212121")),
    "retake": (colors.HexColor("#546E7A"), colors.white),
    "routine": (colors.HexColor("#2E7D32"), colors.white),
}

PAGE_W, PAGE_H = A4
MARGIN = 14 * mm
CONTENT_W = PAGE_W - 2 * MARGIN

S = {
    "body": ParagraphStyle("body", fontName="Sans", fontSize=8.3, leading=10.6),
    "small": ParagraphStyle("small", fontName="Sans", fontSize=7.2, leading=9, textColor=MUTED),
    "h2": ParagraphStyle("h2", fontName="Sans-Bold", fontSize=9.6, leading=12, textColor=BRAND, spaceBefore=3.5, spaceAfter=2),
    "label": ParagraphStyle("label", fontName="Sans", fontSize=7.2, leading=9, textColor=MUTED),
    "value": ParagraphStyle("value", fontName="Sans-Bold", fontSize=8.3, leading=10.4),
    "banner": ParagraphStyle("banner", fontName="Sans-Bold", fontSize=7.6, leading=9.6, textColor=colors.HexColor("#8A4B00")),
}


def _p(text, style="body", **kw) -> Paragraph:
    text = "" if text is None else str(text)
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(text, ParagraphStyle(f"{style}-x", parent=S[style], **kw) if kw else S[style])


def _kv(rows, width: float, label_frac: float = 0.42) -> Table:
    tbl = Table([[_p(k, "label"), _p(v, "value")] for k, v in rows],
                colWidths=[width * label_frac, width * (1 - label_frac)])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1.4), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return tbl


def _image(path: Optional[str], max_w: float, max_h: float, max_px: int = 480):
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


def _bar(pct: int, width: float, top: bool) -> Drawing:
    d = Drawing(width, 8)
    d.add(Rect(0, 1, width, 6, fillColor=BRAND_LIGHT, strokeColor=None))
    d.add(Rect(0, 1, max(0.5, width * pct / 100), 6, fillColor=BRAND if top else colors.HexColor("#9FB8BF"),
               strokeColor=None))
    return d


def _score_bars(scores, width: float) -> Table:
    """One row per grade: wrapped label | bar | percentage (labels can be long, e.g. Romanian)."""
    lw, bw, pw = width * 0.50, width * 0.36, width * 0.14
    rows = [[_p(label, "value" if top else "body", fontSize=7.2, leading=8.6), _bar(pct, bw - 4, top),
             _p(f"{pct}%", "value" if top else "body", fontSize=7.2, leading=8.6, alignment=2)]
            for label, pct, top in scores]
    tbl = Table(rows, colWidths=[lw, bw, pw])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0.8),
                             ("BOTTOMPADDING", (0, 0), (-1, -1), 0.8)]))
    return tbl


def _dot(color) -> Drawing:
    from reportlab.graphics.shapes import Circle

    d = Drawing(8, 9)
    d.add(Circle(4, 4.5, 3, fillColor=color, strokeColor=None))
    return d


def _qr(url: str, size: float) -> Drawing:
    widget = QrCodeWidget(url)
    x1, y1, x2, y2 = widget.getBounds()
    d = Drawing(size, size, transform=[size / (x2 - x1), 0, 0, size / (y2 - y1), 0, 0])
    d.add(widget)
    return d


def _box(content, bg, border=None, pad=5) -> Table:
    tbl = Table([[content]], colWidths=[CONTENT_W])
    style = [("BACKGROUND", (0, 0), (-1, -1), bg), ("LEFTPADDING", (0, 0), (-1, -1), pad + 2),
             ("RIGHTPADDING", (0, 0), (-1, -1), pad + 2), ("TOPPADDING", (0, 0), (-1, -1), pad),
             ("BOTTOMPADDING", (0, 0), (-1, -1), pad + 1)]
    if border is not None:
        style.append(("BOX", (0, 0), (-1, -1), 0.7, border))
    tbl.setStyle(TableStyle(style))
    return tbl


def _two_cols(left, right, gap=6 * mm, left_frac=0.5) -> Table:
    lw = (CONTENT_W - gap) * left_frac
    tbl = Table([[left, "", right]], colWidths=[lw, gap, CONTENT_W - gap - lw])
    tbl.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                             ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return tbl


def build_passport_pdf(
    *,
    case: dict,
    patient: Optional[dict],
    history: list[dict],
    image_path: Optional[str],
    heatmap_path: Optional[str],
    lang: str,
    confidence_threshold: float = 0.6,
    public: bool = False,
    share_url: Optional[str] = None,
    share_expires_at: Optional[str] = None,
) -> bytes:
    """Render the passport for one case and return the PDF bytes."""
    report = build_report(case=case, patient=patient, history=history, lang=lang,
                          confidence_threshold=confidence_threshold, public=public,
                          share_url=share_url, share_expires_at=share_expires_at)
    c, x = report["codes"], report["text"]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN, topMargin=25 * mm, bottomMargin=19 * mm,
        title=f"{x['title']} · {case['case_id']}", author="RetinaAI Nexus (research prototype)", subject=x["subtitle"],
    )

    def decorate(canvas, doc_):
        canvas.saveState()
        canvas.setFillColor(BRAND)
        canvas.rect(0, PAGE_H - 19 * mm, PAGE_W, 19 * mm, stroke=0, fill=1)
        canvas.setFillColor(colors.white)
        canvas.setFont("Sans-Bold", 15)
        canvas.drawString(MARGIN, PAGE_H - 10.5 * mm, x["title"])
        canvas.setFont("Sans", 8.3)
        canvas.drawString(MARGIN, PAGE_H - 15.5 * mm, f"RetinaAI Nexus · {x['subtitle']}")
        canvas.setFont("Sans-Bold", 9)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 10.5 * mm, case["case_id"])
        canvas.setFont("Sans", 8)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 15.5 * mm, x["language"])
        # footer: traceability + disclaimer
        canvas.setStrokeColor(LINE)
        canvas.line(MARGIN, 15 * mm, PAGE_W - MARGIN, 15 * mm)
        canvas.setFillColor(MUTED)
        canvas.setFont("Sans", 6.8)
        canvas.drawString(MARGIN, 11.5 * mm, x["footer_trace"][:190])
        canvas.drawString(MARGIN, 8 * mm, x["disclaimer"][:200])
        canvas.drawRightString(PAGE_W - MARGIN, 4.5 * mm, str(doc_.page))
        canvas.restoreState()

    story: list = []
    banner = x["banner"] + (f"  ·  {x['shared_note']}" if x["shared_note"] else "")
    story += [_box(_p(banner, "banner"), colors.HexColor("#FFF3E0"), colors.HexColor("#FFB74D"), pad=3), Spacer(1, 4)]

    # ---------------- A · patient & screening (+ QR on shared copies)
    half = (CONTENT_W - 6 * mm) / 2
    if x["share_url"]:
        qr_w = 26 * mm
        col = (CONTENT_W - qr_w - 8 * mm) / 2
        qr_cell = [_qr(x["share_url"], 18 * mm), _p(f"{x['share']}. {x['valid_until']}", "small", fontSize=6.4, leading=7.6)]
        a = Table([[_kv(x["patient_rows"], col), "", _kv(x["screening_rows"], col), qr_cell]],
                  colWidths=[col, 4 * mm, col + 4 * mm, qr_w])
        a.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    else:
        a = _two_cols(_kv(x["patient_rows"], half), _kv(x["screening_rows"], half))
    story += [_p(x["sections"]["sec_a"], "h2"), a]

    # ---------------- B · screening result
    bg, fg = LEVEL_COLORS.get(c["level"], (BRAND, colors.white))
    grade_line = Table(
        [[_p(f"{x['ai_grade_label']}: {x['ai_grade']}", "value", textColor=fg, fontSize=11.5, leading=14),
          _p(x["top_score"], "value", textColor=fg, alignment=2)]],
        colWidths=[CONTENT_W * 0.66 - 14, CONTENT_W * 0.34 - 14])
    grade_line.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                                    ("VALIGN", (0, 0), (-1, -1), "BOTTOM")]))
    result_box = _box([
        grade_line,
        _p(f"{x['triage_label_caption']}: {x['triage_label']}", "value", textColor=fg, fontSize=9.6, leading=12.5),
        _p(x["triage_action"], "body", textColor=fg),
    ], bg)
    status_color = WARN if c["clinical_status"] == "pending_review" else (
        OK if c["clinical_status"] in ("confirmed", "modified") else MUTED)
    status_box = _box([
        _p(f"{x['clinical_status_caption']}: {x['clinical_status']}", "value", textColor=status_color),
        _p(x["clinical_status_detail"], "body") if x["clinical_status_detail"] else Spacer(1, 0),
    ], colors.white, status_color, pad=4)
    story += [_p(x["sections"]["sec_b"], "h2"), result_box, Spacer(1, 3), status_box, Spacer(1, 3),
              _p(x["result_statement"], "body"), Spacer(1, 2), _p(x["limits_note"], "small")]

    # ---------------- C · imaging   +   D · model output
    img_w = (CONTENT_W - 6 * mm) * 0.27
    img_h = 33 * mm if x["share_url"] else 42 * mm
    original = _image(image_path, img_w, img_h)
    heat = _image(heatmap_path, img_w, img_h)
    imgs = Table([[_p(x["original_caption"], "label"), _p(x["heatmap_caption"], "label")],
                  [original or _p("—", "small"), heat or _p(x["heatmap_note"], "small")]],
                 colWidths=[img_w + 2 * mm, img_w + 2 * mm])
    imgs.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    c_block = [_p(x["sections"]["sec_c"], "h2"), imgs]
    if heat:
        c_block.append(_p(x["heatmap_note"], "small"))
    d_w = CONTENT_W - 2 * img_w - 10 * mm
    d_block = [_p(x["sections"]["sec_d"], "h2")]
    if x["scores"]:
        d_block += [_score_bars(x["scores"], d_w), _p(x["scores_caption"], "small")]
    else:
        d_block.append(_p(x["ai_grade"], "small"))
    cd = Table([[c_block, d_block]], colWidths=[2 * img_w + 6 * mm, d_w + 4 * mm])
    cd.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether(cd))

    # ---------------- E · TrustGate & next steps
    tg_rows = []
    for label, value, good in x["trustgate"]:
        tg_rows.append([_dot(OK if good else WARN), _p(label, "label"), _p(value, "value")])
    tg = Table(tg_rows, colWidths=[5 * mm, half * 0.45, half * 0.55 - 5 * mm])
    tg.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                            ("TOPPADDING", (0, 0), (-1, -1), 1.2), ("BOTTOMPADDING", (0, 0), (-1, -1), 1.2),
                            ("LINEBELOW", (0, 0), (-1, -2), 0.3, LINE)]))
    why = [_p(x["why_title"], "value")] + [_p(f"• {w}", "body") for w in x["why"]] + [_p(x["thresholds_note"], "small")]
    left = [tg, Spacer(1, 4), _p(x["followup_caption"], "value"),
            _kv(x["followup_rows"], half, 0.38) if x["followup_rows"] else _p("—", "small")]
    story.append(KeepTogether([_p(x["sections"]["sec_e"], "h2"), _two_cols(left, why)]))

    # ---------------- F · history
    f_block = [_p(x["sections"]["sec_f"], "h2")]
    if x["history_compare"]:
        rows = [[_p(k, "label"), _p(v, "value"), _p(d, "small")] for k, v, d in x["history_compare"]]
        cmp_tbl = Table(rows, colWidths=[CONTENT_W * 0.28, CONTENT_W * 0.5, CONTENT_W * 0.22])
        cmp_tbl.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 1),
                                     ("BOTTOMPADDING", (0, 0), (-1, -1), 1)]))
        f_block += [cmp_tbl, _p(f"{x['history_status']} {x['history_note']}".strip(), "body")]
    else:
        f_block.append(_p(x["history_status"], "small"))
    f_block.append(_p(x["eye_note"], "small"))
    story.append(KeepTogether(f_block))

    # ---------------- emergency safety note (always)
    story += [Spacer(1, 5), _box(_p(x["emergency_note"], "value", textColor=colors.HexColor("#7F0000")),
                                 colors.HexColor("#FDECEA"), colors.HexColor("#E57373"), pad=4)]

    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
