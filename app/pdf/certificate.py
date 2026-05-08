"""
Certificate PDF generator.
Supports a background image, configurable colours, and a configurable font
(ReportLab built-in names or a TTF file path via cert_font).
"""
import io
import os

_LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'static', 'lkc-logo.jpeg')


def _dimmed_logo_reader(opacity: float = 0.07):
    """Return a ReportLab ImageReader for the LKC logo at the given opacity (0–1)."""
    if not os.path.exists(_LOGO_PATH):
        return None
    try:
        from PIL import Image as PILImage
        from reportlab.lib.utils import ImageReader
        img = PILImage.open(_LOGO_PATH).convert('RGBA')
        r, g, b, a = img.split()
        a = a.point(lambda v: int(v * opacity))
        img.putalpha(a)
        buf = io.BytesIO()
        img.save(buf, 'PNG')
        buf.seek(0)
        return ImageReader(buf)
    except Exception:
        return None


def generate_certificate(
    event_name: str,
    participant_name: str,
    item_name: str,
    category: str,
    position: str,
    event_date: str,
    bg_image_path: str = None,
    title_text: str = 'Certificate of Achievement',
    body_template: str = None,
    font_colour: str = '#1a1a2e',
    heading_colour: str = '#8b6914',
    title_colour: str = '#1a1a2e',
    name_colour: str = '#8b6914',
    cert_font: str = None,
    cert_logo_path: str = None,
) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import HexColor
    except ImportError:
        raise RuntimeError('reportlab is required')

    # ── Font setup ────────────────────────────────────────────────────────────
    from app.pdf.fonts import resolve_pdf_fonts
    base_font, bold_font = resolve_pdf_fonts(cert_font)

    page_w, page_h = landscape(A4)
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))

    # ── Background ────────────────────────────────────────────────────────────
    if bg_image_path and os.path.exists(bg_image_path):
        c.drawImage(bg_image_path, 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, mask='auto')
    else:
        c.setFillColor(HexColor('#f5f0e8'))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        c.setStrokeColor(HexColor('#8b6914'))
        c.setLineWidth(3)
        c.rect(15 * mm, 15 * mm, page_w - 30 * mm, page_h - 30 * mm, fill=0, stroke=1)
        c.setLineWidth(1)
        c.rect(18 * mm, 18 * mm, page_w - 36 * mm, page_h - 36 * mm, fill=0, stroke=1)

    # ── Watermark ─────────────────────────────────────────────────────────────
    if not (bg_image_path and os.path.exists(bg_image_path)):
        wm = _dimmed_logo_reader(opacity=0.07)
        if wm:
            wm_size = 160 * mm
            c.drawImage(wm, (page_w - wm_size) / 2, (page_h - wm_size) / 2,
                        width=wm_size, height=wm_size,
                        preserveAspectRatio=True, mask='auto')

    def _hex(val, fallback):
        return HexColor(val if val and val.startswith('#') else fallback)

    text_colour = _hex(font_colour,    '#1a1a2e')
    heading_col = _hex(heading_colour, '#8b6914')
    title_col   = _hex(title_colour,   '#1a1a2e')
    name_col    = _hex(name_colour,    '#8b6914')

    # ── Logo ──────────────────────────────────────────────────────────────────
    # Use cert_logo_path if provided, fall back to bundled lkc-logo.jpeg
    _logo = cert_logo_path if (cert_logo_path and os.path.exists(cert_logo_path)) else _LOGO_PATH
    if os.path.exists(_logo):
        logo_h = 24 * mm
        c.drawImage(_logo,
                    (page_w - logo_h) / 2, page_h - 48 * mm,
                    width=logo_h, height=logo_h,
                    preserveAspectRatio=True, mask='auto')

    # ── Event name ────────────────────────────────────────────────────────────
    c.setFillColor(heading_col)
    c.setFont(bold_font, 20)
    c.drawCentredString(page_w / 2, page_h - 60 * mm, event_name)

    # ── Certificate title ─────────────────────────────────────────────────────
    c.setFont(bold_font, 30)
    c.setFillColor(title_col)
    c.drawCentredString(page_w / 2, page_h - 76 * mm, title_text)

    # ── Decorative line ───────────────────────────────────────────────────────
    c.setStrokeColor(HexColor('#8b6914'))
    c.setLineWidth(1.5)
    c.line(60 * mm, page_h - 82 * mm, page_w - 60 * mm, page_h - 82 * mm)

    # ── Body text ─────────────────────────────────────────────────────────────
    body_y = page_h - 102 * mm
    c.setFont(base_font, 13)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y, 'This is to certify that')

    c.setFont(bold_font, 22)
    c.setFillColor(name_col)
    c.drawCentredString(page_w / 2, body_y - 14 * mm, participant_name)

    c.setFont(base_font, 13)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y - 26 * mm, f'has achieved  {position}  in')

    c.setFont(bold_font, 16)
    c.setFillColor(title_col)
    c.drawCentredString(page_w / 2, body_y - 38 * mm, f'{item_name}  —  {category}')

    c.setFont(base_font, 12)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y - 52 * mm,
                        f'at  {event_name}  on  {event_date}')

    # ── Signature lines ───────────────────────────────────────────────────────
    sig_y = 30 * mm
    c.setStrokeColor(HexColor('#8b6914'))
    c.setLineWidth(1)
    c.line(60 * mm, sig_y, 120 * mm, sig_y)
    c.line(page_w - 120 * mm, sig_y, page_w - 60 * mm, sig_y)
    c.setFont('Helvetica', 9)
    c.setFillColor(HexColor('#555555'))
    c.drawCentredString(90 * mm, sig_y - 5 * mm, 'President')
    c.drawCentredString(page_w - 90 * mm, sig_y - 5 * mm, 'Secretary')

    c.save()
    return buf.getvalue()
