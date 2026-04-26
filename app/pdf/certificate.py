"""
Certificate PDF generator.
Supports a background image and customisable text layout from EventConfig.
"""
import io
import os


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
) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib import colors
        from reportlab.lib.units import mm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.colors import HexColor
    except ImportError:
        raise RuntimeError('reportlab is required')

    page_w, page_h = landscape(A4)
    buf = io.BytesIO()

    c = rl_canvas.Canvas(buf, pagesize=landscape(A4))

    # Background image
    if bg_image_path and os.path.exists(bg_image_path):
        c.drawImage(bg_image_path, 0, 0, width=page_w, height=page_h,
                    preserveAspectRatio=False, mask='auto')
    else:
        # Default gradient-like background
        c.setFillColor(HexColor('#f5f0e8'))
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
        # Decorative border
        c.setStrokeColor(HexColor('#8b6914'))
        c.setLineWidth(3)
        c.rect(15 * mm, 15 * mm, page_w - 30 * mm, page_h - 30 * mm,
               fill=0, stroke=1)
        c.setLineWidth(1)
        c.rect(18 * mm, 18 * mm, page_w - 36 * mm, page_h - 36 * mm,
               fill=0, stroke=1)

    text_colour = HexColor(font_colour if font_colour.startswith('#') else '#1a1a2e')

    # Organisation name
    c.setFillColor(HexColor('#8b6914'))
    c.setFont('Helvetica-Bold', 11)
    c.drawCentredString(page_w / 2, page_h - 35 * mm, 'Association Kalamela Management System')

    # Event name
    c.setFillColor(text_colour)
    c.setFont('Helvetica', 10)
    c.drawCentredString(page_w / 2, page_h - 44 * mm, event_name)

    # Title
    c.setFont('Helvetica-Bold', 28)
    c.setFillColor(HexColor('#1a1a2e'))
    c.drawCentredString(page_w / 2, page_h - 70 * mm, title_text)

    # Decorative line
    c.setStrokeColor(HexColor('#8b6914'))
    c.setLineWidth(1.5)
    c.line(60 * mm, page_h - 76 * mm, page_w - 60 * mm, page_h - 76 * mm)

    # Body
    body_y = page_h - 96 * mm
    c.setFont('Helvetica', 13)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y, 'This is to certify that')

    c.setFont('Helvetica-Bold', 22)
    c.setFillColor(HexColor('#8b6914'))
    c.drawCentredString(page_w / 2, body_y - 14 * mm, participant_name)

    c.setFont('Helvetica', 13)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y - 26 * mm,
                        f'has achieved  {position}  in')

    c.setFont('Helvetica-Bold', 16)
    c.setFillColor(HexColor('#1a1a2e'))
    c.drawCentredString(page_w / 2, body_y - 38 * mm,
                        f'{item_name}  —  {category}')

    c.setFont('Helvetica', 12)
    c.setFillColor(text_colour)
    c.drawCentredString(page_w / 2, body_y - 52 * mm,
                        f'at  {event_name}  on  {event_date}')

    # Signature line
    sig_y = 30 * mm
    c.setStrokeColor(HexColor('#8b6914'))
    c.setLineWidth(1)
    c.line(60 * mm, sig_y, 120 * mm, sig_y)
    c.line(page_w - 120 * mm, sig_y, page_w - 60 * mm, sig_y)
    c.setFont('Helvetica', 9)
    c.setFillColor(HexColor('#555555'))
    c.drawCentredString(90 * mm, sig_y - 5 * mm, 'Organiser')
    c.drawCentredString(page_w - 90 * mm, sig_y - 5 * mm, 'Chairperson')

    c.save()
    return buf.getvalue()
