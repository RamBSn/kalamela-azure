"""
Chest Number PDF generator.
Produces A4 portrait PDF with 2 chest number cards per page.
"""
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas


def _auto_font_size(c, text, font_name, max_w, max_h, max_size=220, min_size=60):
    """Return the largest font size where text fits within max_w and cap height fits max_h."""
    for size in range(max_size, min_size - 1, -2):
        if c.stringWidth(text, font_name, size) <= max_w and size * 0.72 <= max_h:
            return size
    return min_size


def _draw_card(c, number_info, event_name, x, y, w, h):
    """Draw one chest-number card. (x, y) is the bottom-left corner."""
    padding_side = 8 * mm
    num_str = str(number_info['number'])

    # ── Border ──────────────────────────────────────────────────────────────
    c.setStrokeColorRGB(0, 0, 0)
    c.setLineWidth(1.5)
    c.rect(x, y, w, h)

    # ── Event name (top) ─────────────────────────────────────────────────────
    event_font_size = 11
    c.setFont('Helvetica-Bold', event_font_size)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawCentredString(x + w / 2, y + h - 12 * mm, event_name.upper())

    # ── Participant name (bottom) ─────────────────────────────────────────────
    name = number_info.get('name', '')
    name_font_size = 13
    c.setFont('Helvetica', name_font_size)
    c.setFillColorRGB(0.2, 0.2, 0.2)
    c.drawCentredString(x + w / 2, y + 9 * mm, name)

    # ── Chest number (centre, auto-sized) ────────────────────────────────────
    reserved_top    = 18 * mm   # event name zone
    reserved_bottom = 20 * mm   # name zone
    num_zone_h = h - reserved_top - reserved_bottom
    num_zone_w = w - 2 * padding_side

    font_size = _auto_font_size(
        c, num_str, 'Helvetica-Bold',
        max_w=num_zone_w,
        max_h=num_zone_h,
        max_size=220,
        min_size=60,
    )

    c.setFont('Helvetica-Bold', font_size)
    # Dark navy for registered; grey for extra/unregistered
    if number_info.get('registered', True):
        c.setFillColorRGB(0.1, 0.1, 0.18)
    else:
        c.setFillColorRGB(0.45, 0.45, 0.45)

    # Vertical centre of the number zone
    cap_h = font_size * 0.72
    zone_centre_y = y + reserved_bottom + num_zone_h / 2
    baseline_y = zone_centre_y - cap_h / 2
    c.drawCentredString(x + w / 2, baseline_y, num_str)


def _draw_divider(c, x_start, y, x_end):
    """Dashed horizontal cut line at y."""
    c.setStrokeColorRGB(0.55, 0.55, 0.55)
    c.setLineWidth(0.5)
    c.setDash(4, 4)
    c.line(x_start, y, x_end, y)
    c.setDash()   # reset


def generate_chest_numbers_pdf(numbers: list, event_name: str) -> bytes:
    """
    numbers: list of {'number': int, 'name': str, 'registered': bool}
    Returns bytes of a PDF with 2 chest-number cards per A4 page.
    """
    buf = io.BytesIO()
    page_w, page_h = A4          # ~595 × 842 pt (portrait)
    margin = 10 * mm

    card_w = page_w - 2 * margin
    card_h = (page_h - 2 * margin) / 2   # exactly half the usable height

    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f'Chest Numbers — {event_name}')

    i = 0
    while i < len(numbers):
        # ── Top card ─────────────────────────────────────────────────────────
        top_y = margin + card_h
        _draw_card(c, numbers[i], event_name, margin, top_y, card_w, card_h)

        # ── Dashed divider ────────────────────────────────────────────────────
        _draw_divider(c, margin, margin + card_h, page_w - margin)

        # ── Bottom card (if available) ────────────────────────────────────────
        if i + 1 < len(numbers):
            _draw_card(c, numbers[i + 1], event_name, margin, margin, card_w, card_h)

        i += 2

        # New page if more cards remain
        if i < len(numbers):
            c.showPage()

    c.save()
    return buf.getvalue()
