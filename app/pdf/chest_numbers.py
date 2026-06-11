"""
Chest Number PDF generator.
Produces A4 portrait PDF with 2 chest number cards per page.
"""
import io
import os
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas


def _auto_font_size(c, text, font_name, max_w, max_h, max_size=220, min_size=60):
    """Return the largest font size where text fits within max_w and cap height fits max_h."""
    for size in range(max_size, min_size - 1, -2):
        if c.stringWidth(text, font_name, size) <= max_w and size * 0.72 <= max_h:
            return size
    return min_size


def _draw_card(c, number_info, event_name, x, y, w, h,
               font_size_override=None, header_img_path=None,
               header_h_mm=25, show_name=True):
    """Draw one chest-number card. (x, y) is the bottom-left corner."""
    padding_side = 8 * mm
    num_str = str(number_info['number'])

    # ── Border ──────────────────────────────────────────────────────────────
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.5)
    c.rect(x, y, w, h)

    # ── Top zone: header image OR event name text ────────────────────────────
    using_header = bool(header_img_path and os.path.exists(header_img_path))
    if using_header:
        header_h_pt = header_h_mm * mm
        reserved_top = header_h_pt + 4 * mm
        c.drawImage(header_img_path, x, y + h - header_h_pt,
                    width=w, height=header_h_pt,
                    preserveAspectRatio=False, mask='auto')
    else:
        reserved_top = 18 * mm
        c.setFont('Helvetica-Bold', 11)
        c.setFillColorRGB(0.35, 0.35, 0.35)
        c.drawCentredString(x + w / 2, y + h - 12 * mm, event_name.upper())

    # ── Participant name (bottom) ─────────────────────────────────────────────
    if show_name:
        name = number_info.get('name', '')
        c.setFont('Helvetica', 7)
        c.setFillColorRGB(0.2, 0.2, 0.2)
        c.drawCentredString(x + w / 2, y + 9 * mm, name)

    # ── Chest number (centre, auto-sized) ────────────────────────────────────
    reserved_bottom = 20 * mm
    num_zone_h = h - reserved_top - reserved_bottom
    num_zone_w = w - 2 * padding_side

    if font_size_override:
        font_size = font_size_override
    else:
        font_size = _auto_font_size(
            c, num_str, 'Helvetica-Bold',
            max_w=num_zone_w,
            max_h=num_zone_h,
            max_size=220,
            min_size=60,
        )

    c.setFont('Helvetica-Bold', font_size)
    if number_info.get('registered', True):
        c.setFillColorRGB(0.1, 0.1, 0.18)
    else:
        c.setFillColorRGB(0.45, 0.45, 0.45)

    cap_h = font_size * 0.72
    # Shift number slightly higher (60% from bottom) when header image is present
    bias = 0.60 if using_header else 0.50
    zone_centre_y = y + reserved_bottom + num_zone_h * bias
    baseline_y = zone_centre_y - cap_h / 2
    c.drawCentredString(x + w / 2, baseline_y, num_str)


def _draw_divider(c, x_start, y, x_end):
    """Dashed horizontal cut line at y."""
    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.5)
    c.setDash(4, 4)
    c.line(x_start, y, x_end, y)
    c.setDash()


def generate_chest_numbers_pdf(numbers: list, event_name: str,
                               font_size: int = None,
                               header_img_path: str = None,
                               header_h_mm: int = 25,
                               show_name: bool = True) -> bytes:
    """
    numbers: list of {'number': int, 'name': str, 'registered': bool}
    Returns bytes of a PDF with 2 chest-number cards per A4 page.
    """
    buf = io.BytesIO()
    page_w, page_h = A4
    margin = 10 * mm
    card_w = page_w - 2 * margin
    card_h = (page_h - 2 * margin) / 2

    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f'Chest Numbers — {event_name}')

    i = 0
    while i < len(numbers):
        top_y = margin + card_h
        _draw_card(c, numbers[i], event_name, margin, top_y, card_w, card_h,
                   font_size_override=font_size, header_img_path=header_img_path,
                   header_h_mm=header_h_mm, show_name=show_name)

        _draw_divider(c, margin, margin + card_h, page_w - margin)

        if i + 1 < len(numbers):
            _draw_card(c, numbers[i + 1], event_name, margin, margin, card_w, card_h,
                       font_size_override=font_size, header_img_path=header_img_path,
                       header_h_mm=header_h_mm, show_name=show_name)

        i += 2
        if i < len(numbers):
            c.showPage()

    c.save()
    return buf.getvalue()
